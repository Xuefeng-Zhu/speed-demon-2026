"""Build independent shared-dictionary experiments from the captured production source."""
from pathlib import Path

here = Path(__file__).resolve().parent
source = (here / "baseline.rs").read_text()
start = source.index("#[derive(Default)]\n/// Open-addressing table")
end = source.index("/// One chunk's records of one hour:", start)
dictionary = '''/// An immutable endpoint, owned once for the entire input. The zero-padded name
/// permits both 64-byte equality loads, including a name of the maximum legal length.
struct Entry {
    hash: u64,
    len: u32,
    id: u32,
    name: [u8; 128],
}

/// Append-only open addressing: OnceLock publishes each slot exactly once. A thread
/// that loses initialization compares the published key before continuing its probe.
struct Dictionary {
    slots: Vec<OnceLock<Box<Entry>>>,
    next_id: AtomicU32,
}

impl Dictionary {
    #[inline(always)]
    fn find(&self, d: &[u8], h: u64, s: usize, e: usize) -> u32 {
        let (mask, n) = (self.slots.len() - 1, e - s);
        let mut i = (h >> 40) as usize & mask;
        loop {
            let entry = self.slots[i].get_or_init(|| {
                let id = self.next_id.fetch_add(1, Ordering::Relaxed);
                assert!(id < 2048, "more endpoints than the spec allows");
                let mut name = [0; 128];
                name[..n].copy_from_slice(&d[s..e]);
                Box::new(Entry { hash: h, len: n as u32, id, name })
            });
            if entry.hash == h && entry.len as usize == n && if n < 64 {
                !eq_mask(&entry.name, 0, Some((d, s)), 0) & ((1 << n) - 1) == 0
            } else {
                !eq_mask(&entry.name, 0, Some((d, s)), 0) == 0
                    && !eq_mask(&entry.name, 64, Some((d, s + 64)), 0) & ((1 << (n - 64)) - 1) == 0
            } {
                return entry.id;
            }
            i = (i + 1) & mask;
        }
    }
}

'''
source = source[:start] + dictionary + source[end:]
source = source.replace("use std::collections::HashMap;\n", "")
source = source.replace("fn parse(d: &[u8], mut i: usize, end: usize, shared: &[Shared], next_id: &AtomicU32)",
                        "fn parse(d: &[u8], mut i: usize, end: usize, shared: &Dictionary)")
source = source.replace("    let mut table = Table::default();\n", "")
old = '''        let id = table.find(d, h, s, e, || {
            let mut map = shared[(h >> 60) as usize].lock().unwrap(); // top 4 bits pick a shard
            *map.entry(d[s..e].to_vec()).or_insert_with(|| next_id.fetch_add(1, Ordering::Relaxed))
        }) as u64;'''
assert source.count(old) == 1
source = source.replace(old, "        let id = shared.find(d, h, s, e) as u64;")
source = source.replace("names: &[Vec<u8>]", "names: &[&[u8]]")
old = '''fn make_plan(shared: &[Shared], parsed: &[Mutex<Vec<Records>>]) -> (Vec<u32>, Vec<Vec<u8>>, Jobs) {
    let mut names: Vec<(Vec<u8>, u32)> = Vec::new();
    for map in shared {
        names.extend(std::mem::take(&mut *map.lock().unwrap()));
    }'''
new = '''fn make_plan<'a>(shared: &'a Dictionary, parsed: &[Mutex<Vec<Records>>]) -> (Vec<u32>, Vec<&'a [u8]>, Jobs) {
    let mut names: Vec<(&[u8], u32)> = shared.slots.iter().filter_map(OnceLock::get)
        .map(|entry| (&entry.name[..entry.len as usize], entry.id)).collect();'''
assert source.count(old) == 1
source = source.replace(old, new)
source = source.replace('''    let shared: Vec<Shared> = (0..SHARDS).map(|_| Mutex::default()).collect();
    let next_id = AtomicU32::new(0);''', '''    let shared = Dictionary {
        slots: (0..4096).map(|_| OnceLock::new()).collect(),
        next_id: AtomicU32::new(0),
    };''')
source = source.replace("OnceLock<(Vec<u32>, Vec<Vec<u8>>, Jobs)>", "OnceLock<(Vec<u32>, Vec<&[u8]>, Jobs)>")
source = source.replace('''            let (tx, shared, next_id, parsed, plan, barrier) =
                (tx.clone(), &shared, &next_id, &parsed, &plan, &barrier);''', '''            let (tx, shared, parsed, plan, barrier) =
                (tx.clone(), &shared, &parsed, &plan, &barrier);''')
source = source.replace("parse(d, start, end, shared, next_id)", "parse(d, start, end, shared)")
source = source.replace('''//!    bucketed by hour. A thread's own endpoint table caches the dense ids (0, 1, 2, ...) handed
//!    out by shared maps (sharded by hash, to spread lock contention) that keep copies of the
//!    names, so no merge is needed and the chunk's pages can be dropped.''', '''//!    bucketed by hour. One shared append-only dictionary owns endpoint names and publishes
//!    dense ids with per-slot OnceLocks; initialized entries are immutable for all workers.
//!    The dictionary copies names, so each parsed input chunk's pages can be dropped.''')
source = source.replace("/// `map_file`; arena reads stay within its 64-byte zero tail.",
                        "/// `map_file`; dictionary reads stay within each entry's 128-byte name.")
source = source.replace("/// Parses the lines in `d[i..end]` into records per hour, with ids from the shared tables.",
                        "/// Parses the lines in `d[i..end]` into records per hour using the shared dictionary.")
(here / "shared-box.rs").write_text(source)
inline = source.replace("Vec<OnceLock<Box<Entry>>>", "Vec<OnceLock<Entry>>")
inline = inline.replace("Box::new(Entry { hash: h, len: n as u32, id, name })",
                        "Entry { hash: h, len: n as u32, id, name }")
(here / "shared-inline.rs").write_text(inline)
print("Generated shared-box.rs and shared-inline.rs")

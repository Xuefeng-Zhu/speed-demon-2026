
/// Profiling only: resident kB of the pages overlapping `p[..len]`, from /proc/self/pagemap.
#[allow(dead_code)]
fn resident<T>(p: *const T, len: usize) -> u64 {
    use std::io::{Read, Seek, SeekFrom};
    if len == 0 {
        return 0;
    }
    let (a, b) = (p as u64 & !4095, (p as u64 + (len * std::mem::size_of::<T>()) as u64 + 4095) & !4095);
    let mut f = fs::File::open("/proc/self/pagemap").unwrap();
    f.seek(SeekFrom::Start(a / 4096 * 8)).unwrap();
    let mut buf = vec![0u8; ((b - a) / 4096 * 8) as usize];
    f.read_exact(&mut buf).unwrap();
    buf.chunks(8).filter(|e| u64::from_le_bytes((*e).try_into().unwrap()) >> 63 == 1).count() as u64 * 4
}

/// Profiling only: resident kB of a vector's whole capacity.
#[allow(dead_code)]
fn res<T>(v: &Vec<T>) -> u64 {
    resident(v.as_ptr(), v.capacity())
}

/// Profiling only: RssAnon in kB.
#[allow(dead_code)]
fn rss_anon() -> u64 {
    let st = fs::read_to_string("/proc/self/status").unwrap();
    st.lines().find(|l| l.starts_with("RssAnon:")).unwrap().split_whitespace().nth(1).unwrap().parse().unwrap()
}

/// Profiling only: anonymous resident kB per mapping class from /proc/self/smaps: malloc arenas
/// of threads (64 MiB aligned heaps), the main heap, and other anonymous mappings (thread stacks,
/// buffers mapped by malloc), printed with a label.
#[allow(dead_code)]
fn smaps(label: &str) {
    let s = fs::read_to_string("/proc/self/smaps").unwrap();
    let (mut arena, mut heap, mut other, mut n_arena, mut start, mut name) = (0u64, 0u64, 0u64, 0, 0u64, String::new());
    for l in s.lines() {
        let f: Vec<&str> = l.split_whitespace().collect();
        if f[0].contains('-') && !f[0].ends_with(':') {
            start = u64::from_str_radix(f[0].split_once('-').unwrap().0, 16).unwrap();
            name = f.get(5).map_or(String::new(), |n| n.to_string());
        } else if f[0] == "Anonymous:" {
            let kb: u64 = f[1].parse().unwrap();
            if name == "[heap]" {
                heap += kb;
            } else if name.is_empty() && start % (64 << 20) == 0 && kb > 0 {
                arena += kb;
                n_arena += 1;
            } else if name.is_empty() {
                other += kb;
            }
        }
    }
    eprintln!("smaps {label} anon_kb {} thread_arenas_kb {arena} n {n_arena} main_heap_kb {heap} other_anon_kb {other}", rss_anon());
}

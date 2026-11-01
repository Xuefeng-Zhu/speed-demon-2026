#!/usr/bin/env python3
"""mkmem.py <src.rs> > <instrumented.rs>: memory instrumentation for Track B main.rs.

Adds, with output to stderr only at the end of the run:
  PHASE <name> <ns>                       end of a phase (same names as b-speed3/tools/mkprof.py)
  MEM <name> <VmHWM> <VmRSS> <RssAnon> <RssFile>        kB, /proc/self/status, right after PHASE
  MALL <name> <arena> <hblks> <hblkhd> <uordblks> <fordblks>   glibc mallinfo2, KiB (hblks a count)
  MEM <name>_trim ...                     with SD_PROF_TRIM=<name>[,<name>]: malloc_trim(0) then MEM
  MIDX <thread> <first> <ndocs> <stream_len> <stream_cap> <docs_len> <offs_len> <hits> <t0> <t_scan> <t_csr>
                                          per chunk (lengths in elements, times in ns)
  MSAMP <ns> <rss_kb> <anon_kb>           with SD_PROF_SAMPLE_US=n: /proc/self/statm every n us
  With SD_PROF_LOCKSTEP=1 a thread that has scanned its r-th chunk waits (up to 300 ms) until
  every thread has, so the CSRs of a round coincide (all threads at the same speed).
Tags differ from experiments/b-linux-profile/run.py's IDX/MEMT formats on purpose.
  INFO <key> <value>                      sizes of structures
  malloc_stats() output (per arena system/in use bytes) after the log.
Anchors are exact strings of the source; a missing optional anchor is skipped with a note on stderr.
"""
import sys

src = open(sys.argv[1]).read()


def rep(a, b, need=True):
    global src
    n = src.count(a)
    if n != 1:
        if need:
            raise SystemExit(f'anchor found {n} times: {a!r}')
        sys.stderr.write(f'skip anchor ({n}): {a[:60]!r}\n')
        return
    src = src.replace(a, b)


HEADER = r'''
// MEMPROF: instrumentation only (experiments/b-mem/profile.rs); output logic unchanged.
static LOG: std::sync::Mutex<String> = std::sync::Mutex::new(String::new());
static T0: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();
static STOP: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
fn ns() -> u64 {
    T0.get().unwrap().elapsed().as_nanos() as u64
}
#[repr(C)]
struct MallInfo2 {
    arena: usize,
    ordblks: usize,
    smblks: usize,
    hblks: usize,
    hblkhd: usize,
    usmblks: usize,
    fsmblks: usize,
    uordblks: usize,
    fordblks: usize,
    keepcost: usize,
}
extern "C" {
    fn mallinfo2() -> MallInfo2;
    fn malloc_stats();
    fn malloc_trim(pad: usize) -> i32;
}
/// Reads a small /proc file into a stack buffer (no heap allocation).
fn proc_read<'a>(path: &str, buf: &'a mut [u8; 4096]) -> &'a str {
    use std::io::Read;
    let mut f = fs::File::open(path).unwrap();
    let mut n = 0;
    while let Ok(k) = f.read(&mut buf[n..]) {
        if k == 0 || n + k >= buf.len() {
            n += k;
            break;
        }
        n += k;
    }
    std::str::from_utf8(&buf[..n]).unwrap()
}
fn status() -> [u64; 4] {
    let mut buf = [0u8; 4096];
    let s = proc_read("/proc/self/status", &mut buf);
    let get = |n: &str| -> u64 {
        s.lines()
            .find(|l| l.starts_with(n) && l[n.len()..].starts_with(':'))
            .and_then(|l| l[n.len() + 1..].split_whitespace().next()?.parse().ok())
            .unwrap_or(0)
    };
    [get("VmHWM"), get("VmRSS"), get("RssAnon"), get("RssFile")]
}
fn mem(name: &str) {
    let v = status();
    let m = unsafe { mallinfo2() };
    let mut log = LOG.lock().unwrap();
    writeln!(log, "MEM {name} {} {} {} {}", v[0], v[1], v[2], v[3]).unwrap();
    writeln!(log, "MALL {name} {} {} {} {} {}", m.arena >> 10, m.hblks, m.hblkhd >> 10, m.uordblks >> 10, m.fordblks >> 10).unwrap();
    let _ = (m.ordblks, m.smblks, m.usmblks, m.fsmblks, m.keepcost);
}
fn phase(name: &str) {
    let t = ns();
    writeln!(LOG.lock().unwrap(), "PHASE {name} {t}").unwrap();
    mem(name);
    if env::var("SD_PROF_TRIM").map_or(false, |v| v.split(',').any(|x| x == name)) {
        unsafe { malloc_trim(0) };
        let v = status();
        writeln!(LOG.lock().unwrap(), "MEM {name}_trim {} {} {} {}", v[0], v[1], v[2], v[3]).unwrap();
    }
}
static NTH: AtomicUsize = AtomicUsize::new(0);
static SCANNED: AtomicUsize = AtomicUsize::new(0);
thread_local! { static ROUND: std::cell::Cell<usize> = const { std::cell::Cell::new(0) }; }
/// With SD_PROF_LOCKSTEP=1: after scanning its r-th chunk a thread waits (up to 300 ms) until
/// every thread has scanned r + 1 chunks, so the CSRs of a round run at the same time, as on
/// a box where all threads scan at the same speed (worst case for the stream + docs overlap).
fn lockstep() {
    let r = ROUND.with(|c| c.replace(c.get() + 1));
    let n = SCANNED.fetch_add(1, Relaxed) + 1;
    if env::var_os("SD_PROF_LOCKSTEP").is_none() || n >= (r + 1) * NTH.load(Relaxed) {
        return;
    }
    let t = ns();
    while SCANNED.load(Relaxed) < (r + 1) * NTH.load(Relaxed) && ns() - t < 300_000_000 {
        thread::sleep(std::time::Duration::from_micros(20));
    }
}
fn info(k: &str, v: usize) {
    writeln!(LOG.lock().unwrap(), "INFO {k} {v}").unwrap();
}
/// With SD_PROF_SAMPLE_US=n: samples /proc/self/statm every n us into a preallocated Vec.
fn sampler() -> Option<thread::JoinHandle<Vec<(u64, u64, u64)>>> {
    let us: u64 = env::var("SD_PROF_SAMPLE_US").ok()?.parse().ok()?;
    let mut v: Vec<(u64, u64, u64)> = Vec::with_capacity(1 << 16);
    Some(thread::spawn(move || {
        let mut buf = [0u8; 4096];
        while !STOP.load(Relaxed) && v.len() < v.capacity() {
            let t = ns();
            let s = proc_read("/proc/self/statm", &mut buf);
            let mut it = s.split_whitespace().map(|x| x.parse::<u64>().unwrap_or(0));
            let (_, rss, shared) = (it.next(), it.next().unwrap_or(0), it.next().unwrap_or(0));
            v.push((t, rss * 4, (rss - shared) * 4));
            thread::sleep(std::time::Duration::from_micros(us));
        }
        v
    }))
}
'''

if "fn malloc_trim" in src:  # the source declares it already
    HEADER = HEADER.replace("    fn malloc_trim(pad: usize) -> i32;\n", "")
rep("use std::{collections::HashMap, env, fs, thread};",
    "use std::{collections::HashMap, env, fs, thread};" + HEADER)

# scan_chunk: per-chunk sizes and times
rep("    let mut stream = Vec::with_capacity((hi - lo) / 16);",
    "    let t_start = ns();\n    let mut stream = Vec::with_capacity((hi - lo) / 16);")
rep("    // Counting sort of the stream",
    "    let (t_scan, slen, scap) = (ns(), stream.len(), stream.capacity());\n    lockstep();\n    // Counting sort of the stream")
rep("    Chunk { first, offs, docs, hits }\n}",
    """    writeln!(LOG.lock().unwrap(), "MIDX {:?} {first} {} {slen} {scap} {} {} {} {t_start} {t_scan} {}",
        thread::current().id(), doc - first, docs.len(), offs.len(), hits.len(), ns()).unwrap();
    Chunk { first, offs, docs, hits }
}""")

# main phases
rep("fn main() {\n", "fn main() {\n    T0.set(std::time::Instant::now()).unwrap();\n    let samp = sampler();\n")
rep("    let mut plan = Plan::default();", "    phase(\"read_queries\");\n    info(\"qtext_bytes\", qtext.len());\n    let mut plan = Plan::default();")
rep('    let data = map_file(&format!("{data_dir}/docs.txt"));',
    '''    phase("parse_intern");
    NTH.store(nthreads, Relaxed);
    info("keys_bytes", plan.keys.capacity() * 24);
    info("qs_cap_bytes", qs.capacity() * std::mem::size_of_val(&qs[0]));
    info("terms_cap_bytes", terms.capacity() * 8);
    info("nterms", plan.role.len());
    let data = map_file(&format!("{data_dir}/docs.txt"));
    phase("mmap");''')
rep("    // A BOOL term in more than 1 of 32", "    phase(\"sample_scan\");\n    // A BOOL term in more than 1 of 32")
if "    // Equal byte ranges, each moved" in src:
    rep("    // Equal byte ranges, each moved", "    phase(\"plan_build\");\n    // Equal byte ranges, each moved")
else:
    rep("    let last = data.rsplit", "    phase(\"plan_build\");\n    let last = data.rsplit")
if "    let nchunks = nthreads *" in src:
    rep("    let nchunks = nthreads *", "    phase(\"rows_alloc\");\n    let nchunks = nthreads *")
else:
    rep("    let m = data.len().div_ceil(nthreads << 24)", "    phase(\"rows_alloc\");\n    let m = data.len().div_ceil(nthreads << 24)")
rep("    chunks.sort_unstable_by_key(|c| c.0);",
    '''    phase("index");
    info("nchunks", chunks.len());
    info("nthreads", nthreads);
    info("nlist", plan.nlist);
    info("nbm", plan.nbm);
    info("rows_bytes", plan.nbm * words * 8);
    chunks.sort_unstable_by_key(|c| c.0);''')
rep("    // Phrase matches as sorted", "    phase(\"chunk_sort\");\n    info(\"docs_bytes\", plan.chunks.iter().map(|c| c.docs.capacity() * 2).sum());\n    info(\"offs_bytes\", plan.chunks.iter().map(|c| c.offs.capacity() * 4).sum());\n    // Phrase matches as sorted")
rep("    // Answer blocks of queries, claimed", "    phase(\"hits_collect\");\n    // Answer blocks of queries, claimed")
rep("    outs.sort_unstable_by_key(|o| o.0);",
    '''    phase("answer");
    info("outs_len", outs.iter().map(|o| o.1.len()).sum());
    info("outs_cap", outs.iter().map(|o| o.1.capacity()).sum());
    outs.sort_unstable_by_key(|o| o.0);''')
rep("    let out: String = outs.into_iter().map(|o| o.1).collect();",
    "    let out: String = outs.into_iter().map(|o| o.1).collect();\n    info(\"out_cap\", out.capacity());", need=False)
rep("    fs::create_dir_all(&out_dir).ok();",
    "    phase(\"outs_sort_concat\");\n    fs::create_dir_all(&out_dir).ok();", need=False)
rep("    std::process::exit(0); // the OS",
    '''    phase("write");
    STOP.store(true, Relaxed);
    if let Some(h) = samp {
        let v = h.join().unwrap();
        let mut log = LOG.lock().unwrap();
        for (t, r, a) in v {
            writeln!(log, "MSAMP {t} {r} {a}").unwrap();
        }
    }
    eprint!("{}", LOG.lock().unwrap());
    unsafe { malloc_stats() };
    std::process::exit(0); // the OS''')
sys.stdout.write(src)

#!/usr/bin/env python3
"""Instrumented copy of a Track B main.rs for the index-tail measurement (test-only).

    python3 mkinst.py src.rs out.rs [--nchunks-env]

Adds, on stderr at exit, in the format experiments/b-linux-profile/run.py parses:
    PHASE rows_alloc <ns>   just before the index threads start
    PHASE index <ns>        after the chunks are collected
    PHASE answer <ns>       after the answer threads are joined
    PHASE write <ns>        after results.txt is written
    INFO nthreads <n>
    IDX <thread> <chunk> 0 <bytes> <t_start> <t_end> <t_end> 0 0 <nhits> <docs_entries>
    MEMK <chunk|index|answer> <ns> <VmRSS KiB> <VmHWM KiB>   at each chunk end and phase end
(ns since the start of main). run.py's IDX summary then gives per-thread busy time,
utilization of the index window and the idle tail (last thread end - first thread end).
The source must contain the patterns below exactly once each; the chunk layout itself is
left as it is, so the same script instruments the baseline and every candidate.
With --nchunks-env (baseline-shaped sources only) the test-only SD_NCHUNKS variable
overrides the chunk count (equal chunks), for tools/sweep.py.
"""
import sys

src = open(sys.argv[1]).read()


def sub(old, new):
    global src
    assert src.count(old) == 1, old
    src = src.replace(old, new)


sub('fn main() {\n', '''static LOG: std::sync::Mutex<Vec<String>> = std::sync::Mutex::new(Vec::new());
static T0: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();
fn now() -> u128 {
    T0.get_or_init(std::time::Instant::now).elapsed().as_nanos()
}
fn log(s: String) {
    LOG.lock().unwrap().push(s);
}
/// MEMK <where> <ns> <VmRSS KiB> <VmHWM KiB> (test-only; reads /proc/self/status)
fn rss(at: &str) {
    let s = fs::read_to_string("/proc/self/status").unwrap_or_default();
    let kb = |k: &str| s.lines().find(|l| l.starts_with(k)).and_then(|l| l.split_whitespace().nth(1)).unwrap_or("0").to_string();
    log(format!("MEMK {at} {} {} {}", now(), kb("VmRSS:"), kb("VmHWM:")));
}
fn inst(tid: usize, k: usize, lo: usize, hi: usize, f: impl FnOnce() -> Chunk) -> Chunk {
    let t0 = now();
    let c = f();
    let t1 = now();
    log(format!("IDX {tid} {k} 0 {} {t0} {t1} {t1} 0 0 {} {}", hi - lo, c.hits.len(), c.docs.len()));
    rss("chunk");
    c
}

fn main() {
    now();
''')
sub('    let next = AtomicUsize::new(0);\n', '    let next = AtomicUsize::new(0);\n    log(format!("PHASE rows_alloc {}", now()));\n')
sub('par(nthreads, |_| {\n        claim(', 'par(nthreads, |tid| {\n        claim(')
# Wrap the scan_chunk call of the claim loop (whatever its arguments) in inst().
call = 'scan_chunk(data, cut(k), cut(k + 1)'
assert src.count(call) == 1, call
a = src.index(call)
depth, j = 0, a + len('scan_chunk')
while True:
    depth += {'(': 1, ')': -1}.get(src[j], 0)
    j += 1
    if depth == 0:
        break
src = src[:a] + 'inst(tid, k, cut(k), cut(k + 1), || ' + src[a:j] + ')' + src[j:]
sub('    chunks.sort_unstable_by_key(|c| c.0);\n', '    log(format!("PHASE index {}", now()));\n    rss("index");\n    chunks.sort_unstable_by_key(|c| c.0);\n')
sub('    outs.sort_unstable_by_key(|o| o.0);\n', '    log(format!("PHASE answer {}", now()));\n    rss("answer");\n    outs.sort_unstable_by_key(|o| o.0);\n')
sub('    std::process::exit(0);', '''    log(format!("PHASE write {}", now()));
    log(format!("INFO nthreads {nthreads}"));
    let mut l = LOG.lock().unwrap();
    l.sort_by_key(|s| !s.starts_with("PHASE")); // stable: PHASE lines first, in order
    eprintln!("{}", l.join("\\n"));
    std::process::exit(0);''')
if '--nchunks-env' in sys.argv[3:]:
    sub('    let nchunks = nthreads * data.len().div_ceil(nthreads << 24).max(1);\n',
        '    let nchunks = env::var("SD_NCHUNKS").ok().and_then(|s| s.parse().ok())'
        '.unwrap_or(nthreads * data.len().div_ceil(nthreads << 24).max(1));\n')
open(sys.argv[2], 'w').write(src)

#!/usr/bin/env python3
"""Writes the screened Track C memory variants into variants/ from baseline.rs (speed-demon f828bd8).

Every variant (and variants/base.rs) adds an SD_THREADS override so 12 and 20 threads (the board's
i5-13500 has 20 hardware threads) can be emulated on the 8-vCPU sandbox. profile.rs additionally
prints per-phase memory to stderr (see README.md). Each replacement must match exactly once."""
import pathlib, sys

HERE = pathlib.Path(__file__).parent
SRC = (HERE / 'baseline.rs').read_text()
OUT = HERE / 'variants'

THREADS = ('let n = thread::available_parallelism().map_or(1, |n| n.get());',
           'let n = thread::available_parallelism().map_or(1, |n| n.get());\n'
           '    let n = env::var("SD_THREADS").map_or(n, |s| s.parse().unwrap());')
BLOCK = lambda b: [('const BLOCK: usize = 1024;', f'const BLOCK: usize = {b};')]
BUF = lambda kib: [('let mut buf = vec![0u8; (1 << 16) + 64];', f'let mut buf = vec![0u8; ({kib} << 10) + 64];')]
# Mark the owner's inbox at every buffer refill instead of once per chunk: bounds the backlog.
MARK_REFILL = [('                    if done {\n                        break;\n                    }\n',
                '                    if done {\n                        break;\n                    }\n'
                '                    mark(&mut agg);\n')]
# Workers that run out of chunks keep emptying their inbox until every worker has sent its
# last block (the chunk counter ends at chunks + n failed claims + n of these increments),
# instead of waiting at the barrier while their inbox fills.
SPIN = [('            barrier.wait();\n            mark(&mut agg);\n            agg\n',
         '            next.fetch_add(1, Release);\n'
         '            while next.load(Acquire) < chunks + 2 * n {\n'
         '                mark(&mut agg);\n'
         '                thread::yield_now();\n'
         '            }\n'
         '            mark(&mut agg);\n            agg\n')]
SPIN_NOYIELD = [(a, b.replace('                thread::yield_now();\n', '')) for a, b in SPIN]
# glibc malloc options set at the start of main: M_ARENA_MAX (-8) and M_TOP_PAD (-2).
MALLOPT = lambda *kv: [('    fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;\n',
                        '    fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;\n    fn mallopt(param: i32, value: i32) -> i32;\n'),
                       ('    let dir = |k, d: &str|',
                        ''.join(f'    unsafe {{ mallopt({k}, {v}) }};\n' for k, v in kv) + '    let dir = |k, d: &str|')]
NOHUGE_REGION = [('let region: &[AtomicU8] = zeroed(max + 1, 14);', 'let region: &[AtomicU8] = zeroed(max + 1, 0);')]
NOHUGE_TABLE = [('let table: &[AtomicU64] = zeroed(5 * m * n, 14);', 'let table: &[AtomicU64] = zeroed(5 * m * n, 0);')]
# Thread stacks of 256 KiB instead of std's 2 MiB (only touched pages count either way).
STACK = [('s.spawn(move || f(t))',
          'thread::Builder::new().stack_size(1 << 18).spawn_scoped(s, move || f(t)).unwrap()')]

VARIANTS = {
    'base': [],
    'blk256': BLOCK(256),
    'blk512': BLOCK(512),
    'blk128': BLOCK(128),
    'buf16': BUF(16),
    'buf32': BUF(32),
    'mark': MARK_REFILL,
    'nohuge-region': NOHUGE_REGION,
    'nohuge': NOHUGE_REGION + NOHUGE_TABLE,
    'stack': STACK,
    'mark-blk256': MARK_REFILL + BLOCK(256),
    'mark-blk256-buf32': MARK_REFILL + BLOCK(256) + BUF(32),
    'blk256-buf32': BLOCK(256) + BUF(32),
    'cand-spin': MARK_REFILL + BLOCK(256) + BUF(32) + SPIN,
    'cand-spin-noyield': MARK_REFILL + BLOCK(256) + BUF(32) + SPIN_NOYIELD,
    'cand-arena1': MARK_REFILL + BLOCK(256) + BUF(32) + MALLOPT((-8, 1)),
    'cand-arena2': MARK_REFILL + BLOCK(256) + BUF(32) + MALLOPT((-8, 2)),
    'cand-toppad0': MARK_REFILL + BLOCK(256) + BUF(32) + MALLOPT((-2, 0)),
    'cand-arena1-toppad0': MARK_REFILL + BLOCK(256) + BUF(32) + MALLOPT((-8, 1), (-2, 0)),
    'mark-blk128-buf32': MARK_REFILL + BLOCK(128) + BUF(32),
    'mark-blk128-buf16': MARK_REFILL + BLOCK(128) + BUF(16),
    'mark-blk256-buf16': MARK_REFILL + BLOCK(256) + BUF(16),
    'mark-blk512-buf32': MARK_REFILL + BLOCK(512) + BUF(32),
}

PROFILE = [
    ('fn main() {',
     '''static BACKLOG: AtomicUsize = AtomicUsize::new(0); // events queued in inboxes now
static BACKLOG_MAX: AtomicUsize = AtomicUsize::new(0);
/// 0 setup, 1 parsing, 2 some worker out of chunks, 3 every block sent (final marks), 4 after
/// the workers. A sampler thread keeps the peak anonymous RSS (statm resident - shared) per stage.
static STAGE: AtomicUsize = AtomicUsize::new(0);
static PEAK: [AtomicUsize; 5] = [const { AtomicUsize::new(0) }; 5];
/// Prints each mapping with more than 64 KiB anonymous, by size class.
fn smaps() {
    let s = fs::read_to_string("/proc/self/smaps").unwrap();
    let (mut head, mut size) = (String::new(), 0);
    for l in s.lines() {
        if l.starts_with("Size:") { size = l.split_whitespace().nth(1).unwrap().parse::<usize>().unwrap(); }
        else if l.starts_with("Anonymous:") {
            let a: usize = l.split_whitespace().nth(1).unwrap().parse().unwrap();
            if a > 64 { eprintln!("SMAPS size_kib={size} anon_kib={a} {head}"); }
        } else if !l.contains(':') || l.split_whitespace().next().unwrap().contains('-') { head = l.to_string(); }
    }
}
fn sampler() {
    thread::spawn(|| loop {
        let s = fs::read_to_string("/proc/self/statm").unwrap();
        let v: Vec<usize> = s.split_whitespace().map(|x| x.parse().unwrap()).collect();
        PEAK[STAGE.load(Relaxed)].fetch_max((v[1] - v[2]) * 4, Relaxed);
        thread::sleep(std::time::Duration::from_micros(20));
    });
}
#[repr(C)]
#[derive(Default, Debug)]
struct Mallinfo2 { arena: usize, ordblks: usize, smblks: usize, hblks: usize, hblkhd: usize,
    usmblks: usize, fsmblks: usize, uordblks: usize, fordblks: usize, keepcost: usize }
extern "C" { fn mallinfo2() -> Mallinfo2; }
fn kb(file: &str, key: &str) -> usize {
    let s = fs::read_to_string(file).unwrap();
    s.lines().find(|l| l.starts_with(key)).map_or(0, |l| l.split_whitespace().nth(1).unwrap().parse().unwrap())
}
/// Prints the phase's high-water mark of non-file RSS (VmHWM - RssFile is not exact, so
/// RssAnon is sampled at the end of the phase and VmHWM reset with clear_refs 5).
fn phase(name: &str) {
    let (hwm, anon, file, huge) = (kb("/proc/self/status", "VmHWM:"), kb("/proc/self/status", "RssAnon:"),
        kb("/proc/self/status", "RssFile:"), kb("/proc/self/smaps_rollup", "AnonHugePages:"));
    let mi = unsafe { mallinfo2() };
    eprintln!("PHASE {name} hwm_kib={hwm} anon_kib={anon} file_kib={file} anon_huge_kib={huge} malloc_arena={} malloc_inuse={} malloc_free={} mmapped={} backlog_max_events={}",
        mi.arena, mi.uordblks, mi.fordblks, mi.hblkhd, BACKLOG_MAX.load(Relaxed));
    fs::write("/proc/self/clear_refs", "5").unwrap();
}

fn main() {
    phase("start");
    sampler();'''),
    ('    let seen: Vec<AtomicU8>',
     '    eprintln!("SIZE region_bytes={} threads={n}", max + 1);\n    let seen: Vec<AtomicU8>'),
    ('        let full = &zeroed',
     '        eprintln!("SIZE table_bytes={} bits={bits}", 5 * m * n * 8);\n        phase("setup");\n        let full = &zeroed'),
    ('                let blocks = std::mem::take(&mut *inbox[t].0.lock().unwrap()); // unlock before the loop',
     '                let blocks = std::mem::take(&mut *inbox[t].0.lock().unwrap()); // unlock before the loop\n'
     '                BACKLOG.fetch_sub(blocks.iter().map(|v| v.len()).sum::<usize>(), Relaxed);'),
    ('                        inbox[owner(h)].0.lock().unwrap().push(full);',
     '                        let b = BACKLOG.fetch_add(BLOCK, Relaxed) + BLOCK;\n'
     '                        BACKLOG_MAX.fetch_max(b, Relaxed);\n'
     '                        inbox[owner(h)].0.lock().unwrap().push(full);'),
    ('            while let Some(c) = claim() {', '            STAGE.fetch_max(1, Relaxed);\n            while let Some(c) = claim() {'),
    ('            for j in 0..RING {', '            STAGE.fetch_max(2, Relaxed); // a worker has no chunk left\n            for j in 0..RING {'),
    ('                inbox[o].0.lock().unwrap().push(v);',
     '                BACKLOG.fetch_add(v.len(), Relaxed);\n                inbox[o].0.lock().unwrap().push(v);'),
    ('            mark(&mut agg);\n            agg\n',
     '            STAGE.fetch_max(3, Relaxed); // all blocks sent\n            mark(&mut agg);\n            agg\n'),
    ('        if !full.load(Relaxed) {',
     '        STAGE.fetch_max(4, Relaxed);\n        smaps();\n        phase("drain");\n        if !full.load(Relaxed) {'),
    ('    fs::write(format!("{out}/aggregates.txt"), text).unwrap();\n',
     '    fs::write(format!("{out}/aggregates.txt"), text).unwrap();\n    phase("output");\n'
     '    eprintln!("PEAK_ANON_KIB setup={} parse={} tail={} final_mark={} after={}", PEAK[0].load(Relaxed),'
     ' PEAK[1].load(Relaxed), PEAK[2].load(Relaxed), PEAK[3].load(Relaxed), PEAK[4].load(Relaxed));\n'),
]


def apply(src, reps, name):
    for a, b in reps:
        if src.count(a) != 1:
            sys.exit(f'{name}: {a!r} matches {src.count(a)} times')
        src = src.replace(a, b)
    return src


OUT.mkdir(exist_ok=True)
for name, reps in VARIANTS.items():
    (OUT / f'{name}.rs').write_text(apply(SRC, [THREADS] + reps, name))
(HERE / 'profile.rs').write_text(apply(SRC, [THREADS] + PROFILE, 'profile'))
for name, reps in VARIANTS.items():
    if reps:
        (OUT / f'profile-{name}.rs').write_text(apply(apply(SRC, [THREADS] + reps, name), PROFILE, 'profile-' + name))
print('wrote', len(VARIANTS), 'variants + profiles')

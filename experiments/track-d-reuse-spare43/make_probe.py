"""Write a timing probe of a Track D source: `python3 make_probe.py SRC OUT`.

The probe takes its thread count from SD_THREADS (default: all CPUs) and prints,
on stderr, the time since the start of `main` and the container's cgroup
memory.current and memory.peak (MB) at five points: start, load (graph built in
the file's ids), renumber, relabel (both graphs in the new ids) and queries.
Answers are unchanged. The same edits apply to the baseline and the candidate.
"""
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src).read()


def rep(old, new):
    global s
    if s.count(old) != 1:
        raise SystemExit(f'{src}: expected one match for {old.strip()[:60]!r}, found {s.count(old)}')
    s = s.replace(old, new)


rep('''    let threads = thread::available_parallelism().map_or(1, |n| n.get());''',
    '''    let t0 = std::time::Instant::now();
    let cg = |f: &str| fs::read_to_string(format!("/sys/fs/cgroup/memory.{f}")).map_or(0.0, |x| x.trim().parse::<f64>().unwrap_or(0.0) / 1e6);
    let mark = |s: &str| eprintln!("{:7.2} ms {s} cur {:.1} peak {:.1}", t0.elapsed().as_secs_f64() * 1e3, cg("current"), cg("peak"));
    mark("start");
    let threads = std::env::var("SD_THREADS").ok().and_then(|x| x.parse().ok()).unwrap_or_else(|| thread::available_parallelism().map_or(1, |n| n.get()));''')
rep('''    let (rank, fwd) = renumber(&g, bits, threads);''', '''    mark("load");
    let (rank, fwd) = renumber(&g, bits, threads);
    mark("renumber");''')
rep('''    let net = Net { graphs, bits, wide };''', '''    mark("relabel");
    let net = Net { graphs, bits, wide };''')
rep('''    let lines = answers.iter()''', '''    mark("queries");
    let lines = answers.iter()''')
open(out, 'w').write(s)

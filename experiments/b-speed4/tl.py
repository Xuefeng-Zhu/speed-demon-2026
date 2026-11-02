#!/usr/bin/env python3
"""Add a timeline to production Track B: tl.py src.rs dst.rs.

Each event records the CLOCK_MONOTONIC time since KB_T0 (set by the parent just
before spawning) and the calling thread's utime, stime and minor faults
(getrusage RUSAGE_THREAD). Events are printed to stderr just before exit.
Thread ids: workers 0..n-1, the setup thread n, main 99, output threads 100+k.
"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()


def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)


rep("use std::fmt::Write as _;\n", """use std::fmt::Write as _;
extern "C" {
    fn clock_gettime(clk: i32, ts: *mut [i64; 2]) -> i32;
    fn getrusage(who: i32, ru: *mut [i64; 18]) -> i32;
}
static T0: AtomicU64 = AtomicU64::new(0);
static EV: Mutex<Vec<(&'static str, usize, usize, u64, [i64; 3])>> = Mutex::new(Vec::new());
fn now() -> u64 {
    let mut ts = [0i64; 2];
    unsafe { clock_gettime(1, &mut ts) };
    ts[0] as u64 * 1_000_000_000 + ts[1] as u64
}
fn ev(l: &'static str, tid: usize, chunk: usize) {
    let t = now() - T0.load(Relaxed);
    let mut ru = [0i64; 18];
    unsafe { getrusage(1, &mut ru) };
    let r = [ru[0] * 1_000_000 + ru[1], ru[2] * 1_000_000 + ru[3], ru[8]];
    EV.lock().unwrap().push((l, tid, chunk, t, r));
}
""")
rep("fn main() {\n", """fn main() {
    T0.store(env::var("KB_T0").ok().and_then(|v| v.parse().ok()).unwrap_or_else(now), Relaxed);
    ev("main", 99, 0);
""")
rep("    let nq = qs.len();\n", "    let nq = qs.len();\n    ev(\"parsed\", 99, 0);\n")
rep("    let data = map_file(&format!(\"{data_dir}/docs.txt\"));\n",
    "    let data = map_file(&format!(\"{data_dir}/docs.txt\"));\n    ev(\"mapped\", 99, 0);\n")
if "    plan.role.push(0);\n    // freq[t]" in s:
    rep("    plan.role.push(0);\n    // freq[t]", "    plan.role.push(0);\n    ev(\"filter\", 99, 0);\n    // freq[t]")
else:  # the filter is built while interning
    rep("    plan.empty = plan.keys.iter().position(|e| e[0] == 0).unwrap();\n", "    plan.empty = plan.keys.iter().position(|e| e[0] == 0).unwrap();\n    ev(\"filter\", 99, 0);\n")
rep("    // A BOOL term in more than 1 of 32 sample documents gets a bitmap,\n",
    "    ev(\"sampled\", 99, 0);\n    // A BOOL term in more than 1 of 32 sample documents gets a bitmap,\n")
rep("    let (next, late) = (AtomicUsize::new(0), std::sync::OnceLock::new());\n",
    "    let (next, late) = (AtomicUsize::new(0), std::sync::OnceLock::new());\n    ev(\"planned\", 99, 0);\n")
rep("""    par(nthreads + 1, |k| {
        if k == nthreads {
""", """    par(nthreads + 1, |k| {
        let tid = k;
        if k == nthreads {
            ev("s_start", tid, 0);
""")
rep("""            _ = late.set(Late { trig, toff, acc: acc.collect() });
            return;""", """            _ = late.set(Late { trig, toff, acc: acc.collect() });
            ev("s_end", tid, 0);
            return;""")
rep("""        let (mut s, mut c) = (Scratch { bm: vec![0; 1024], ..Default::default() }, Chunk::default());
        let chunks""", """        ev("w_start", tid, 0);
        let (mut s, mut c) = (Scratch { bm: vec![0; 1024], ..Default::default() }, Chunk::default());
        let chunks""")
rep("""            let (lo, hi) = (cut(k), cut(k + 1));
            let n = if hi < data.len() { id_at(data, hi) as usize } else { ndocs };
            if lo < hi {
                scan_chunk(&mut c, data, lo, hi, n - id_at(data, lo) as usize, &plan);
                answer(&c, &plan, late.wait(), &mut s);
            }
        }
    });""", """            ev("c_claim", tid, k);
            let (lo, hi) = (cut(k), cut(k + 1));
            let n = if hi < data.len() { id_at(data, hi) as usize } else { ndocs };
            if lo < hi {
                scan_chunk(&mut c, data, lo, hi, n - id_at(data, lo) as usize, &plan);
                ev("c_scanned", tid, k);
                let l = late.wait();
                ev("c_waited", tid, k);
                answer(&c, &plan, l, &mut s);
                ev("c_answered", tid, k);
            }
        }
        ev("w_end", tid, 0);
    });
    ev("joined", 99, 0);""")
rep("""    let outs = par(nthreads, |k| {
        let mut out = String::new();""", """    let outs = par(nthreads, |k| {
        ev("o_start", 100 + k, 0);
        let mut out = String::new();""")
rep("""            out.push('\\n');
        }
        out
    });""", """            out.push('\\n');
        }
        ev("o_end", 100 + k, 0);
        out
    });
    ev("formatted", 99, 0);""")
rep("""    std::process::exit(0); // the OS frees everything faster than the destructors""",
    """    ev("written", 99, 0);
    let mut log = String::new();
    for (l, tid, c, t, r) in EV.lock().unwrap().iter() {
        writeln!(log, "EV {l} {tid} {c} {t} {} {} {}", r[0], r[1], r[2]).unwrap();
    }
    eprint!("{log}");
    std::process::exit(0); // the OS frees everything faster than the destructors""")
open(dst, 'w').write(s)

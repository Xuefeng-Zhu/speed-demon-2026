#!/usr/bin/env python3
"""Writes prof/src/main.rs: track-d/src/main.rs plus diagnostic counters.
Search logic is unchanged; only timers and counters are added."""
import sys
src = open(sys.argv[1]).read()

def rep(a, b, count=1):
    global src
    assert src.count(a) == count, (src.count(a), a[:70])
    src = src.replace(a, b)

prelude = r'''
mod prof {
    use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
    use std::time::Instant;
    pub static T0: std::sync::OnceLock<Instant> = std::sync::OnceLock::new();
    pub fn now() -> f64 { T0.get_or_init(Instant::now).elapsed().as_secs_f64() * 1e3 }
    extern "C" { fn getrusage(who: i32, r: *mut [i64; 18]) -> i32; }
    pub fn usage() -> (f64, f64, i64) {
        let mut r = [0i64; 18];
        unsafe { getrusage(0, &mut r) };
        (r[0] as f64 * 1e3 + r[1] as f64 / 1e3, r[2] as f64 * 1e3 + r[3] as f64 / 1e3, r[8])
    }
    static LAST: std::sync::Mutex<(f64, f64, f64, i64)> = std::sync::Mutex::new((0.0, 0.0, 0.0, 0));
    pub fn mark(label: &str) {
        let (t, (u, s, f)) = (now(), usage());
        let mut l = LAST.lock().unwrap();
        eprintln!("PHASE {label:<14} wall {:6.1} ms  user {:6.1}  sys {:6.1}  minflt {:6}  (at {:6.1})",
            t - l.0, u - l.1, s - l.2, f - l.3, t);
        *l = (t, u, s, f);
    }
    pub static PAR: AtomicU64 = AtomicU64::new(0);
    pub fn par_report(times: &[(f64, f64)], start: f64) {
        let k = PAR.fetch_add(1, Relaxed);
        let busy: Vec<f64> = times.iter().map(|t| t.1 - t.0).collect();
        let first = times.iter().map(|t| t.0 - start).fold(0.0, f64::max);
        let end = times.iter().map(|t| t.1).fold(0.0, f64::max) - start;
        let mean = busy.iter().sum::<f64>() / busy.len() as f64;
        let max = busy.iter().cloned().fold(0.0, f64::max);
        let min = busy.iter().cloned().fold(f64::MAX, f64::min);
        eprintln!("PAR {k} wall {end:6.2} ms  busy min {min:6.2} mean {mean:6.2} max {max:6.2}  last-start {first:5.2}");
    }
    thread_local! {
        pub static POPS: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
        pub static STALE: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
        pub static RELAX: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
        pub static IMPROVE: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
        pub static REDIST: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
    }
    pub fn bump(c: &'static std::thread::LocalKey<std::cell::Cell<u64>>, n: u64) { c.with(|x| x.set(x.get() + n)); }
    pub fn take(c: &'static std::thread::LocalKey<std::cell::Cell<u64>>) -> u64 { c.with(|x| x.replace(0)) }
}
'''
rep('use std::{fs, fs::File, os::fd::AsRawFd, thread};', 'use std::{fs, fs::File, os::fd::AsRawFd, thread};\n' + prelude)

# Per-thread timing of every `parallel` call.
rep('''    thread::scope(|sc| {
        let handles: Vec<_> = (0..threads).map(|i| sc.spawn(move || f(i))).collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    })''', '''    let start = prof::now();
    let (out, times): (Vec<T>, Vec<(f64, f64)>) = thread::scope(|sc| {
        let handles: Vec<_> = (0..threads).map(|i| sc.spawn(move || { let a = prof::now(); let r = f(i); (r, (a, prof::now())) })).collect();
        handles.into_iter().map(|h| h.join().unwrap()).unzip()
    });
    prof::par_report(&times, start);
    out''')

# Load phase split: parse/bucket vs CSR build.
rep('    let (mut buckets, big): (Vec<_>, Vec<_>) = parts.into_iter().unzip();',
    '    prof::mark("parse+bucket");\n    let (mut buckets, big): (Vec<_>, Vec<_>) = parts.into_iter().unzip();')
rep('    first[n] = m as u32;\n    (Csr { first, adj }, bits, big.concat())',
    '    first[n] = m as u32;\n    prof::mark("csr build");\n    (Csr { first, adj }, bits, big.concat())')

# relabel split.
rep('    drop(rank);\n    ends(f, threads);', '    prof::mark("relabel heads");\n    drop(rank);\n    ends(f, threads);\n    prof::mark("in-degree sums");')

# Search counters.
rep('''        me.size -= 1;
        let d = me.get(u);''', '''        me.size -= 1;
        prof::bump(&prof::POPS, 1);
        let d = me.get(u);''')
rep('            continue; // stale: already expanded from an earlier bucket',
    '            prof::bump(&prof::STALE, 1);\n            continue; // stale: already expanded from an earlier bucket')
rep('''            if me.reach(v, d + w as u64) {''', '''            prof::bump(&prof::RELAX, 1);
            if me.reach(v, d + w as u64) {
                prof::bump(&prof::IMPROVE, 1);''')
rep('''            b.drain(..).for_each(|(k, v)| self.push(key(k), v));''',
    '''            prof::bump(&prof::REDIST, b.len() as u64);
            b.drain(..).for_each(|(k, v)| self.push(key(k), v));''')

# main: phase marks and per-query records.
rep('''    unsafe { mallopt(-3, 1 << 17) };''', '''    prof::now();
    prof::mark("start");
    unsafe { mallopt(-3, 1 << 17) };''')
rep('''    let (rank, fwd) = renumber(&g, bits, threads);
    drop(g);''', '''    let (rank, fwd) = renumber(&g, bits, threads);
    prof::mark("renumber");
    drop(g);
    prof::mark("drop g");''')
rep('''    let n = rank.len();
    let graphs''', '''    let n = rank.len();
    prof::mark("queries+wide");
    let graphs''')
rep('''    let net = Net { graphs, bits, wide };''', '''    prof::mark("backward scatter");
    let net = Net { graphs, bits, wide };
    let recs = std::sync::Mutex::new(Vec::new());''')
rep('''            let (mut d, cut) = distance(&mut narrow, &net, s, t);
            if cut && d >= u32::MAX as u64 {''', '''            let q0 = prof::now();
            let (mut d, cut) = distance(&mut narrow, &net, s, t);
            let fell = cut && d >= u32::MAX as u64;
            if cut && d >= u32::MAX as u64 {''')
rep('''            answers[i].store(d as i64, Relaxed);''', '''            answers[i].store(d as i64, Relaxed);
            let c = [&prof::POPS, &prof::STALE, &prof::RELAX, &prof::IMPROVE, &prof::REDIST].map(prof::take);
            recs.lock().unwrap().push((i, prof::now() - q0, c, fell, d as i64));''')
rep('''    let lines = answers.iter()''', '''    prof::mark("queries");
    for (i, ms, c, fell, d) in recs.into_inner().unwrap() {
        eprintln!("Q {i} {ms:.4} {} {} {} {} {} {} {d}", c[0], c[1], c[2], c[3], c[4], fell as u8);
    }
    let lines = answers.iter()''')
rep('''    std::process::exit(0);''', '''    prof::mark("write");
    std::process::exit(0);''')
rep('    let lines = answers.iter()', '    prof::mark("dump profile");\n    let lines = answers.iter()')

# renumber split: BFS growth, row copy, root search (per thread).
rep('''        let (mut mine, mut seed) = (Vec::with_capacity(CLUSTER), None);''', '''        let (mut mine, mut seed) = (Vec::with_capacity(CLUSTER), None);
        let (mut tg, mut tc, mut tf, mut clusters) = (0f64, 0f64, 0f64, 0u64);
        let mut tf0 = prof::now();''')
rep('''            mine.push(root as u32);
            let mut k = 0;''', '''            tf += prof::now() - tf0;
            let g0 = prof::now();
            mine.push(root as u32);
            let mut k = 0;''')
rep('''            // The cluster is complete: number it and move its rows.''', '''            let c0 = prof::now();
            (tg, clusters) = (tg + c0 - g0, clusters + 1);
            // The cluster is complete: number it and move its rows.''')
rep('''                    a[p as usize].store(e, Relaxed);
                    p += 1;
                }
            }
        }''', '''                    a[p as usize].store(e, Relaxed);
                    p += 1;
                }
            }
            tf0 = prof::now();
            tc += tf0 - c0;
        }
        eprintln!("RENUM grow {tg:6.2} copy {tc:6.2} find-root {tf:6.2} ms clusters {clusters}");''')
open(sys.argv[2], 'w').write(src)

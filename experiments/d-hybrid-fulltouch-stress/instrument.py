#!/usr/bin/env python3
"""Produce a diagnostic-only hybrid source with query-state counters.

The output is NOT the contest source: it adds atomic work and stderr output.
"""
import argparse
import hashlib
from pathlib import Path

EXPECTED = "671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c"
ap = argparse.ArgumentParser()
ap.add_argument("--source", type=Path, required=True)
ap.add_argument("--output", type=Path, required=True)
a = ap.parse_args()
raw = a.source.read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED, "unexpected candidate; refuse instrumentation"
s = raw.decode()

def replace_once(old, new):
    global s
    assert s.count(old) == 1, ("unexpected source pattern count", s.count(old), old[:60])
    s = s.replace(old, new, 1)

anchor = "const NONE: u64 = u64::MAX;"
replace_once(anchor, anchor + '''
// Diagnostic only. Relaxed atomics are sufficient for telemetry; all worker
// threads join before the final counters are read.
static PROBE_NARROW_TOUCH: AtomicUsize = AtomicUsize::new(0);
static PROBE_WIDE_TOUCH: AtomicUsize = AtomicUsize::new(0);
static PROBE_CUTOFF: AtomicUsize = AtomicUsize::new(0);
static PROBE_EXHAUST: AtomicUsize = AtomicUsize::new(0);
static PROBE_WIDE_RUNS: AtomicUsize = AtomicUsize::new(0);
static PROBE_WIDE_ACTIVE: AtomicUsize = AtomicUsize::new(0);
static PROBE_WIDE_MAX_ACTIVE: AtomicUsize = AtomicUsize::new(0);
static PROBE_BARRIER_AT: AtomicUsize = AtomicUsize::new(0);
static PROBE_BARRIER_THREADS: AtomicUsize = AtomicUsize::new(0);
static PROBE_BARRIER_ARRIVED: AtomicUsize = AtomicUsize::new(0);
static PROBE_BARRIER_TIMEOUT_SECONDS: AtomicU64 = AtomicU64::new(90);
''')

# The override is diagnostic only: on a VM exposing fewer than 12 CPUs it
# intentionally oversubscribes to exercise all 12 workers' search state.
old = "    let threads = thread::available_parallelism().map_or(1, |n| n.get()).min(12);"
new = '''    let threads = std::env::var("SD_STRESS_THREADS").ok()
        .map(|s| s.parse::<usize>().expect("SD_STRESS_THREADS"))
        .unwrap_or_else(|| thread::available_parallelism().map_or(1, |n| n.get()))
        .clamp(1, 12);
    let barrier_at = std::env::var("SD_STRESS_BARRIER_AT").ok()
        .map(|s| s.parse::<usize>().expect("SD_STRESS_BARRIER_AT"))
        .unwrap_or(0);
    let barrier_timeout = std::env::var("SD_STRESS_BARRIER_TIMEOUT_SECONDS").ok()
        .map(|s| s.parse::<u64>().expect("SD_STRESS_BARRIER_TIMEOUT_SECONDS"))
        .unwrap_or(90).clamp(1, 300);
    PROBE_BARRIER_AT.store(barrier_at, Relaxed);
    PROBE_BARRIER_THREADS.store(threads, Relaxed);
    PROBE_BARRIER_TIMEOUT_SECONDS.store(barrier_timeout, Relaxed);'''
replace_once(old, new)

old = '''struct Search {
    dist: Vec<[u64; 2]>,'''
new = '''struct Search {
    probe_barrier_seen: bool,
    dist: Vec<[u64; 2]>,'''
replace_once(old, new)
old = '''        Search {
            dist: vec![[0; 2]; n],'''
new = '''        Search {
            probe_barrier_seen: false,
            dist: vec![[0; 2]; n],'''
replace_once(old, new)
old = '''            self.heaps[side].push(d, v);
            return true;'''
new = '''            self.heaps[side].push(d, v);
            let at = PROBE_BARRIER_AT.load(Relaxed);
            if at != 0 && !self.probe_barrier_seen && self.touched.len() >= at {
                self.probe_barrier_seen = true;
                PROBE_BARRIER_ARRIVED.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let started = std::time::Instant::now();
                while PROBE_BARRIER_ARRIVED.load(std::sync::atomic::Ordering::SeqCst)
                    < PROBE_BARRIER_THREADS.load(Relaxed) {
                    if started.elapsed() >= std::time::Duration::from_secs(
                        PROBE_BARRIER_TIMEOUT_SECONDS.load(Relaxed)) {
                        eprintln!("SD_STRESS_BARRIER_TIMEOUT arrived={} required={} touched_threshold={}",
                            PROBE_BARRIER_ARRIVED.load(Relaxed),
                            PROBE_BARRIER_THREADS.load(Relaxed), at);
                        std::process::exit(86);
                    }
                    thread::yield_now();
                }
            }
            return true;'''
replace_once(old, new)

old = '''        for &v in &self.touched {
            self.dist[v as usize] = [0; 2];
        }'''
new = '''        PROBE_WIDE_TOUCH.fetch_max(self.touched.len(), Relaxed);
''' + old
replace_once(old, new)

old = '''        for &v in &self.touched {self.dist[v as usize]=[0;2];}
        self.touched.clear();self.heaps.iter_mut().for_each(FastHeap::clear);'''
new = '''        PROBE_NARROW_TOUCH.fetch_max(self.touched.len(), Relaxed);
        if dropped { PROBE_CUTOFF.fetch_add(1, Relaxed); }
        if exhausted { PROBE_EXHAUST.fetch_add(1, Relaxed); }
''' + old
replace_once(old, new)

old = '''                        fallback.get_or_insert_with(|| Search::new(fwd.first.len() - 1))
                            .distance([&fwd, &bwd], s, t)'''
new = '''                        PROBE_WIDE_RUNS.fetch_add(1, Relaxed);
                        let active = PROBE_WIDE_ACTIVE.fetch_add(1, Relaxed) + 1;
                        PROBE_WIDE_MAX_ACTIVE.fetch_max(active, Relaxed);
                        let answer = fallback.get_or_insert_with(|| Search::new(fwd.first.len() - 1))
                            .distance([&fwd, &bwd], s, t);
                        PROBE_WIDE_ACTIVE.fetch_sub(1, Relaxed);
                        answer'''
replace_once(old, new)

old = '''    fs::write(format!("{out}/distances.txt"), text).unwrap();'''
new = old + '''
    eprintln!("SD_STRESS_METRICS narrow_touch_max={} wide_touch_max={} cutoff_queries={} pool_exhaust_queries={} wide_runs={} wide_active_max={} wide_barrier_arrived={}",
        PROBE_NARROW_TOUCH.load(Relaxed), PROBE_WIDE_TOUCH.load(Relaxed),
        PROBE_CUTOFF.load(Relaxed), PROBE_EXHAUST.load(Relaxed),
        PROBE_WIDE_RUNS.load(Relaxed), PROBE_WIDE_MAX_ACTIVE.load(Relaxed),
        PROBE_BARRIER_ARRIVED.load(Relaxed));'''
replace_once(old, new)
a.output.write_text(s)
print(f"diagnostic source={a.output} base_sha256={EXPECTED}")

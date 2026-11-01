#!/usr/bin/env python3
"""instrument.py SRC OUT: copies a Track A main.rs and adds a 100 us sampler thread that records
(ms since the start of main, RssAnon kB, size of the output file so far) and, at the end of main,
prints to stderr the peak RssAnon, the peak of RssAnon + output, and a coarse time series.
Local sandbox profiling only."""
import sys

src, out = sys.argv[1:3]
s = open(src).read()
sampler = '''
    static STOP: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
    let t0 = std::time::Instant::now();
    let out_file = format!("{}/summary.txt", env::var("SD_OUT").unwrap_or_else(|_| "/out".into()));
    let sampler = thread::spawn(move || {
        let mut series = Vec::new();
        while !STOP.load(std::sync::atomic::Ordering::Relaxed) {
            let st = fs::read_to_string("/proc/self/status").unwrap();
            let kb = |k: &str| -> u64 {
                st.lines().find(|l| l.starts_with(k)).map_or(0, |l| l.split_whitespace().nth(1).unwrap().parse().unwrap())
            };
            let o = fs::metadata(&out_file).map_or(0, |m| m.len() / 1024);
            series.push((t0.elapsed().as_secs_f64() * 1e3, kb("RssAnon:"), o, kb("VmPTE:")));
            thread::sleep(std::time::Duration::from_micros(100));
        }
        series
    });
'''
end = '''
    STOP.store(true, std::sync::atomic::Ordering::Relaxed);
    let series = sampler.join().unwrap();
    let anon = series.iter().map(|s| s.1).max().unwrap_or(0);
    let live = series.iter().map(|s| s.1 + s.2).max().unwrap_or(0);
    let at = series.iter().max_by_key(|s| s.1 + s.2).map_or(0.0, |s| s.0);
    eprintln!("mem anon_peak_kb {anon} live_peak_kb {live} live_peak_at_ms {at:.1}");
    let step = (series.len() / 40).max(1);
    for s in series.iter().step_by(step) {
        eprintln!("mem t {:.1} anon_kb {} out_kb {} pte_kb {}", s.0, s.1, s.2, s.3);
    }
'''
i = s.index('fn main() {') + len('fn main() {')
s = s[:i] + sampler + s[i:]
j = s.rindex('}')
s = s[:j] + end + s[j:]
open(out, 'w').write(s)

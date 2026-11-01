#!/usr/bin/env python3
"""instrument.py SRC OUT ANCHOR@@LABEL...

Writes a profiling copy of a Track D main.rs: adds `mark(label)`, which prints
elapsed ms, RssAnon, AnonHugePages and the phase peak of non-file RSS
(VmHWM - RssFile) to stderr and then resets VmHWM (`/proc/self/clear_refs` 5),
so each PHASE line shows the peak reached since the previous mark. Adds an
SD_THREADS override and marks at start and before exit. Each ANCHOR@@LABEL
inserts `mark(LABEL)` after the (unique) anchor text, or before it when LABEL
starts with `^`; `\\n` in an anchor is a newline. Not for submission.
"""
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
def rep(a, b, req=True):
    global s
    if s.count(a) != 1:
        if req: raise SystemExit('anchor: ' + a)
        return
    s = s.replace(a, b)
rep('/// Runs `f(i)`', '''static T0: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();
fn mark(label: &str) {
    let t = T0.get_or_init(std::time::Instant::now).elapsed().as_secs_f64() * 1e3;
    let st = fs::read_to_string("/proc/self/status").unwrap();
    let kb = |k: &str| -> i64 { st.lines().find(|l| l.starts_with(k)).map_or(0, |l| l[k.len()..].split_whitespace().next().unwrap().parse().unwrap()) };
    let (hwm, anon, file) = (kb("VmHWM:"), kb("RssAnon:"), kb("RssFile:"));
    let roll = fs::read_to_string("/proc/self/smaps_rollup").unwrap_or_default();
    let thp = roll.lines().find(|l| l.starts_with("AnonHugePages:")).map_or(0, |l| l[14..].split_whitespace().next().unwrap().parse::<i64>().unwrap());
    eprintln!("PHASE {label} t_ms={t:.2} anon_kb={anon} thp_kb={thp} phase_peak_nonfile_kb={}", hwm - file);
    fs::write("/proc/self/clear_refs", "5").unwrap();
}

/// Runs `f(i)`''')
rep('    let threads = thread::available_parallelism().map_or(1, |n| n.get());', '''    let threads = std::env::var("SD_THREADS").ok().and_then(|t| t.parse().ok()).unwrap_or_else(|| thread::available_parallelism().map_or(1, |n| n.get()));
    mark("start");''')
for a in sys.argv[3:]:
    anchor, label = a.split('@@')
    anchor = anchor.replace('\\n', '\n')
    if label.startswith('^'):
        rep(anchor, f'    mark("{label[1:]}");\n' + anchor, False)
    else:
        rep(anchor, anchor + f'\n    mark("{label}");', False)
rep('    std::process::exit(0);', '    mark("output");\n    std::process::exit(0);')
open(dst, 'w').write(s)

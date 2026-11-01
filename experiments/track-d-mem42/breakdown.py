#!/usr/bin/env python3
"""breakdown.py RUNS THREADS OUT.json BIN...

Runs instrumented Track D binaries (built from profile-*.rs, see instrument.py)
interleaved on full seed 1 with SD_THREADS=THREADS, and reports for every phase
the mean time and the largest per-phase peak of non-file RSS (VmHWM minus
RssFile at the phase end; VmHWM is reset at each phase boundary), plus the
largest AnonHugePages seen. Local sandbox measurements, not board results.
"""
import json, os, shutil, statistics as st, subprocess, sys, tempfile

runs, threads, out, bins = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4:]
data = os.environ.get('SD_DATA', '/projects/sandbox/.data/d-full')
res = {b: {} for b in bins}
for _ in range(runs):
    for b in bins:
        o = tempfile.mkdtemp(dir='/dev/shm')
        env = dict(os.environ, SD_DATA=data, SD_OUT=o, SD_THREADS=threads)
        err = subprocess.run([b], env=env, capture_output=True, text=True, check=True).stderr
        shutil.rmtree(o)
        prev = 0.0
        for line in err.splitlines():
            if not line.startswith('PHASE '):
                continue
            f = dict(x.split('=') for x in line.split()[2:])
            label, t = line.split()[1], float(f['t_ms'])
            if label != 'start':
                r = res[b].setdefault(label, {'ms': [], 'peak_mb': [], 'thp_mb': []})
                r['ms'].append(t - prev)
                r['peak_mb'].append(int(f['phase_peak_nonfile_kb']) / 1024)
                r['thp_mb'].append(int(f['thp_kb']) / 1024)
            prev = t
summary = {}
for b in bins:
    name = os.path.basename(b)
    summary[name] = {k: {'mean_ms': round(st.mean(v['ms']), 2), 'max_peak_mb': round(max(v['peak_mb']), 2),
                         'max_thp_mb': round(max(v['thp_mb']), 2)} for k, v in res[b].items()}
    total = sum(v['mean_ms'] for v in summary[name].values())
    peak = max(v['max_peak_mb'] for v in summary[name].values())
    print(f'{name} (threads {threads}, {runs} runs): total {total:.1f} ms, peak {peak:.1f} MB')
    for k, v in summary[name].items():
        print(f"  {k:22s} {v['mean_ms']:7.2f} ms  peak {v['max_peak_mb']:6.2f} MB  thp {v['max_thp_mb']:5.1f} MB")
json.dump({'runs': runs, 'threads': threads, 'note': 'sandbox, not board results', 'phases': summary},
          open(out, 'w'), indent=1)

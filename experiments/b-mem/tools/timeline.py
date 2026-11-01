#!/usr/bin/env python3
"""timeline.py <bin> <threads> [step_ms] [env=val ...]: one run with the statm sampler (100 us),
prints phases with MEM/MALL lines, the anon RSS series every step_ms, the sampled max and when it
happened, and the IDX lines (per chunk start/scan/csr times in ms)."""
import os, subprocess, sys, tempfile, shutil
D = '/projects/sandbox/.data'
b, t = sys.argv[1], sys.argv[2]
step = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
env = dict(os.environ, SD_DATA=D + '/speed-b-full', SD_THREADS=t, SD_PROF_SAMPLE_US='100')
for kv in sys.argv[4:]:
    k, v = kv.split('=', 1); env[k] = v
o = tempfile.mkdtemp(dir=D + '/mem'); env['SD_OUT'] = o
p = subprocess.run([b if '/' in b else D + '/bin/' + b], env=env, capture_output=True, text=True)
shutil.rmtree(o)
ph, memt, idx, other = [], [], [], []
for l in p.stderr.splitlines():
    x = l.split()
    if not x:
        continue
    if x[0] == 'PHASE': ph.append((x[1], int(x[2]) / 1e6))
    elif x[0] == 'MSAMP': memt.append((int(x[1]) / 1e6, int(x[2]), int(x[3])))
    elif x[0] == 'MIDX': idx.append(x)
    elif x[0] in ('MEM', 'MALL', 'INFO'): other.append(l)
print('\n'.join(other))
print('phases:', ' '.join(f'{n}@{v:.1f}' for n, v in ph))
if memt:
    top = max(memt, key=lambda m: m[2])
    print(f'samples {len(memt)}; max anon {top[2]} kB at {top[0]:.1f} ms (rss {top[1]})')
    nxt = 0
    line = []
    for m in memt:
        if m[0] >= nxt:
            line.append(f'{m[0]:.0f}:{m[2] // 1024}')
            nxt = m[0] + step
    print('anon MB series:', ' '.join(line))
for x in idx:
    # IDX thread first ndocs slen scap docs offs hits t0 tscan tcsr
    print('IDX', x[1], 'first', x[2], 'ndocs', x[3], f'slen {int(x[4]) * 2 >> 10}K cap {int(x[5]) * 2 >> 10}K docs {int(x[6]) * 2 >> 10}K',
          f't0 {int(x[9]) / 1e6:.1f} scan_end {int(x[10]) / 1e6:.1f} csr_end {int(x[11]) / 1e6:.1f}')

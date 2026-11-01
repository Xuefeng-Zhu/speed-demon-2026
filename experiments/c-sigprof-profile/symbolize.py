# usage: SD_DATA=/path/to/c-full SD_OUT=/tmp/prof-out symbolize.py BINARY RUNS CPUS
# Line-level and stage-level CPU profile from the prof.rs sampler (see README.md).
import subprocess, sys, collections, os, re
b, runs, cpus = sys.argv[1], int(sys.argv[2]), sys.argv[3]
env = dict(os.environ)
out_dir = env.setdefault('SD_OUT', '/tmp/prof-out')
os.makedirs(out_dir, exist_ok=True)
segs = []  # (file_offset, vaddr) of LOAD segments
for l in subprocess.run(['readelf', '-lW', b], capture_output=True, text=True).stdout.splitlines():
    f = l.split()
    if f and f[0] == 'LOAD': segs.append((int(f[1], 16), int(f[2], 16)))
addrs = collections.Counter(); other = collections.Counter(); libc = collections.Counter(); total = 0
for r in range(runs):
    subprocess.run(['taskset', '-c', cpus, b], env=env, check=True)
    maps = []; 
    for l in open(os.path.join(out_dir, 'prof.txt')):
        if l.startswith('M '):
            f = l.split(); lo, hi = (int(x, 16) for x in f[1].split('-'))
            maps.append((lo, hi, int(f[3], 16), f[6] if len(f) > 6 else f'[anon {f[2]}]'))
        else:
            rip = int(l, 16); total += 1
            m = next((m for m in maps if m[0] <= rip < m[1]), None)
            if m and m[3] == os.path.abspath(b):
                off = rip - m[0] + m[2]
                seg = max((s for s in segs if s[0] <= off), key=lambda s: s[0])
                addrs[off - seg[0] + seg[1]] += 1
            elif m and 'libc' in m[3]:
                libc[rip - m[0] + m[2]] += 1
            else:
                other[os.path.basename(m[3]) if m else '?'] += 1
keys = list(addrs)
out = subprocess.run(['addr2line', '-f', '-i', '-C', '-a', '-e', b] + [hex(a) for a in keys], capture_output=True, text=True).stdout.splitlines()
# parse: each address block starts with 0x..., then pairs (func, file:line) innermost first
info = {}; cur = None
i = 0
while i < len(out):
    if out[i].startswith('0x'):
        cur = int(out[i], 16); info[cur] = []; i += 1
    else:
        info[cur].append((out[i], out[i + 1])); i += 2
lines = collections.Counter(); funcs = collections.Counter(); mainlines = collections.Counter()
for a, c in addrs.items():
    chain = info.get(a, [('?', '?')])
    fn, loc = chain[0]
    loc = re.sub(r'.*/', '', loc).split(' ')[0]
    lines[f'{loc} [{fn[:50]}]'] += c; funcs[fn[:70]] += c
    # outermost frame in main.rs (the source line in our file that led here)
    for fn2, loc2 in chain:
        if 'main.rs' in loc2:
            mainlines[re.sub(r'.*/', '', loc2).split(' ')[0]] += c; break
    else:
        mainlines['(no main.rs frame)'] += c
print(f'samples {total} over {runs} runs ({total/runs*0.2:.0f} ms CPU per run); outside binary: ' + ', '.join(f'{k} {v/total:.1%}' for k, v in other.most_common(6)))
print('\n== innermost main.rs line (inlined helpers attributed to their call site in main.rs) ==')
for k, v in mainlines.most_common(40): print(f'{v/total:6.1%}  {k}')
print('\n== innermost location ==')
for k, v in lines.most_common(25): print(f'{v/total:6.1%}  {k}')

# libc: file offset -> symbol (text segment offset == vaddr for libc's first LOAD with offset 0 alignment)
lsegs = []
for l in subprocess.run(['readelf', '-lW', '/lib64/libc.so.6'], capture_output=True, text=True).stdout.splitlines():
    f = l.split()
    if f and f[0] == 'LOAD': lsegs.append((int(f[1], 16), int(f[2], 16)))
syms = sorted((int(f[0], 16), f[2]) for f in (l.split() for l in subprocess.run(['nm', '/lib64/libc.so.6'], capture_output=True, text=True).stdout.splitlines()) if len(f) == 3 and f[1] in 'tTwW')
import bisect
lc = collections.Counter()
for off, c in libc.items():
    seg = max((x for x in lsegs if x[0] <= off), key=lambda x: x[0]); va = off - seg[0] + seg[1]
    j = bisect.bisect_right(syms, (va, '~')) - 1
    lc[syms[j][1] if j >= 0 else '?'] += c
print('\n== libc symbols ==')
for k, v in lc.most_common(12): print(f'{v/total:6.1%}  {k}')

import json
ranges = json.loads(os.environ.get('CATS', '[]'))
cat = collections.Counter()
for k, v in mainlines.items():
    try: ln = int(k.split(':')[1])
    except: cat['other/unknown'] += v; continue
    name = next((r[2] for r in ranges if r[0] <= ln <= r[1]), f'other main.rs')
    cat[name] += v
for k, v in lc.items():
    cat['libc ' + ('syscall (futex)' if k == 'syscall' else k if k in ('madvise',) else 'other')] += v
print('\n== by stage ==')
for k, v in cat.most_common(): print(f'{v/total:6.1%}  {k}')

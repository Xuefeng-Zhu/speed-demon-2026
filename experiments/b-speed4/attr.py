#!/usr/bin/env python3
"""Attribute perf cpu-clock samples of a binary to main.rs functions and lines,
following inlining: each sample goes to the innermost main.rs frame.
attr.py perf.data binary [top]"""
import collections, subprocess, sys

data, binary = sys.argv[1], sys.argv[2]
top = int(sys.argv[3]) if len(sys.argv) > 3 else 40
out = subprocess.run(['perf', 'script', '-i', data, '-F', 'ip,sym,symoff,dso', '--no-demangle'],
                     capture_output=True, text=True).stdout
syms = {}
for l in subprocess.run(['nm', binary], capture_output=True, text=True).stdout.splitlines():
    p = l.split()
    if len(p) == 3:
        syms[p[2]] = int(p[0], 16)
ips = collections.Counter()
other = collections.Counter()
total = 0
for line in out.splitlines():
    parts = line.split()
    if len(parts) < 2:
        continue
    total += 1
    sym, dso = parts[1], parts[-1]
    if binary.split('/')[-1] in dso and '+0x' in sym:
        name, off = sym.rsplit('+0x', 1)
        if name in syms:
            ips[syms[name] + int(off, 16)] += 1
        else:
            other['nosym'] += 1
    else:
        other[dso.strip('()').split('/')[-1]] += 1
# Map runtime ips to file offsets: the binary is PIE; perf script prints the
# file-relative address for the main executable when given -F ip? Use as is.
addrs = sorted(ips)
# addr2line -i prints a variable number of (func, file:line) pairs per address;
# use a sentinel-separated second call to split them.
chains = []
res2 = subprocess.run(['addr2line', '-i', '-f', '-C', '-e', binary],
                      input='\n'.join(hex(a) + '\n0x0' for a in addrs) + '\n',
                      capture_output=True, text=True).stdout.splitlines()
i = 0
cur = []
pairs = list(zip(res2[0::2], res2[1::2]))
k = 0
for a in addrs:
    chain = []
    while k < len(pairs) and not (pairs[k][1].startswith('??') and pairs[k][0] == '??'):
        chain.append(pairs[k])
        k += 1
    # skip the sentinel's pairs (one '??' pair)
    while k < len(pairs) and pairs[k][0] == '??' and pairs[k][1].startswith('??'):
        k += 1
        break
    chains.append(chain)
byfunc = collections.Counter()
byline = collections.Counter()
for a, chain in zip(addrs, chains):
    n = ips[a]
    f = l = None
    for func, loc in chain:  # innermost first
        if 'main.rs' in loc:
            f, l = func, loc.split('/')[-1].split(' ')[0]
            break
    if f is None:
        f = l = chain[0][0] if chain else '?'
    byfunc[f.replace('solution::', '')[:80]] += n
    byline[l] += n
print(f'total samples {total}, in binary {sum(ips.values())}')
for d, n in other.most_common(5):
    print(f'  other {d}: {100 * n / total:.1f}%')
print('-- by innermost main.rs function')
for f, n in byfunc.most_common(top):
    print(f'{100 * n / total:6.2f}%  {f}')
print('-- by innermost main.rs line')
for l, n in byline.most_common(top):
    print(f'{100 * n / total:6.2f}%  {l}')
# Phase view: first matching marker in the inline chain (innermost first).
markers = ['masks', 'each_token', 'key', 'hash', 'slot', 'prefetch', 'boolean', 'add', 'answer', 'for_each_doc', 'scan_chunk', 'intern', 'grow', 'main']
byphase = collections.Counter()
for a, chain in zip(addrs, chains):
    names = [f.replace('solution::', '').split('<')[0].split('::')[0] for f, loc in chain if 'main.rs' in loc]
    full = ' > '.join(names)
    ph = 'other'
    if 'answer' in names or 'boolean' in names:
        ph = 'answer:' + next((m for m in names if m in ('boolean', 'add', 'post', 'answer')), names[0])
    elif 'scan_chunk' in names or 'for_each_doc' in names:
        ph = 'scan:' + next((m for m in names if m in markers), names[0] if names else '?')
    elif names:
        ph = 'main:' + names[0]
    byphase[ph] += ips[a]
print('-- by phase')
for p, n in byphase.most_common(40):
    print(f'{100 * n / total:6.2f}%  {p}')

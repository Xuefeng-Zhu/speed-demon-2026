#!/usr/bin/env python3
"""Independent empty-state reference test for B, incl. bitmap cap and workers."""
import itertools
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit('usage: review.py CANDIDATE_RS OFFICIAL_B_REFERENCE_PY')
source = Path(sys.argv[1]).resolve(strict=True).read_text()
reference = Path(sys.argv[2]).resolve(strict=True)
thread_line = 'let nthreads = thread::available_parallelism().map_or(4, |n| n.get());'
cap_line = 'let bitmap_limit = 64 * 1024 * 1024 / nthreads;'
assert source.count(thread_line) == source.count(cap_line) == 1
terms = ['a', 'b', 'c', 'z', 'never', 'missing']
queries = []
for n in range(1, 7):
    for ops in itertools.product(('AND','OR','NOT'), repeat=n-1):
        for shift in range(6):
            order = [terms[(i+shift)%6] for i in range(n)]
            queries.append('BOOL ' + order[0] + ''.join(' '+op+' '+term for op,term in zip(ops,order[1:])))
rng = random.Random(1742)
for _ in range(1800):
    n = rng.randint(1,6)
    q = 'BOOL ' + rng.choice(terms)
    for i in range(n-1): q += ' ' + rng.choice(('AND','OR','NOT')) + ' ' + rng.choice(terms)
    queries.append(q)
queries.extend(['PHRASE "a b"','PHRASE "a a"','PHRASE "never a"']*3)
# Alternate queries that make r dense, prove empty via AND, then revive via OR,
# and an immediately following query that must not see any stale bits.
queries.extend(['BOOL a OR b','BOOL a AND never OR c','BOOL never AND a OR b NOT c','BOOL never','BOOL a AND never NOT b OR z']*64)

with tempfile.TemporaryDirectory(prefix='knownempty-review-') as tmp:
    tmp = Path(tmp)
    specs = [(1,None),(2,None),(3,None),(7,None),(12,None),(32,None),(7,0),(7,8)]
    bins = []
    for j,(workers,cap) in enumerate(specs):
        s = source.replace(thread_line, f'let nthreads = {workers};')
        if cap is not None: s = s.replace(cap_line, f'let bitmap_limit = {cap};')
        src = tmp / f's{j}.rs'; exe = tmp / f'e{j}'
        src.write_text(s)
        subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True)
        bins.append(exe)
    total = 0
    for n in (0,1,2,7,8,63,64,65,129):
        data = tmp / f'data{n}'; ref = tmp / f'ref{n}'; data.mkdir(); ref.mkdir()
        rows=[]
        for i in range(n):
            mask=(i*13+i//7)%16
            words=[terms[k] for k in range(4) if (mask>>k)&1]
            # Extra repeats and non-ASCII bytes ensure tokenization remains exercised.
            if i%5 == 0: words += ['a','a']
            rows.append(f'{i}\t'+' — '.join(words)+'\n')
        (data/'docs.txt').write_text(''.join(rows))
        (data/'queries.txt').write_text('\n'.join(queries)+'\n')
        subprocess.run([sys.executable,str(reference),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
        expected=(ref/'results.txt').read_bytes()
        for j,exe in enumerate(bins):
            out=tmp/f'out{n}-{j}';out.mkdir()
            env=dict(os.environ, SD_DATA=str(data),SD_OUT=str(out))
            subprocess.run([str(exe)],env=env,check=True,stdout=subprocess.DEVNULL)
            actual=(out/'results.txt').read_bytes()
            if actual!=expected:
                raise SystemExit(f'mismatch N={n} workers/cap={specs[j]}')
            assert sorted(p.name for p in out.iterdir())==['results.txt']
            total += len(queries)
    print(f'PASS {total} reference queries ({len(queries)} per fixture) across {len(specs)} worker/cap builds and 9 document counts')

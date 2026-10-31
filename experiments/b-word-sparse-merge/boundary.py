#!/usr/bin/env python3
"""Check sparse threshold selection, high IDs, word edges and exact results."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
src = (HERE / 'candidate.rs').read_text()
needle = 'if sparse_cost <= SPARSE_WORD_BUDGET {'
assert src.count(needle) == src.count('        r.fill(0);') == 1
src = src.replace(needle, needle + '\n            eprintln!("PATH {qi} {sparse_cost} sparse");')
src = src.replace('        r.fill(0);', '        eprintln!("PATH {qi} {sparse_cost} dense");\n        r.fill(0);')

with tempfile.TemporaryDirectory(prefix='sd-b-word-boundary-') as tmp:
    p = Path(tmp)
    source, binary = p / 'trace.rs', p / 'trace'
    source.write_text(src)
    subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(source),'-o',str(binary)], check=True)
    data, out, ref = p/'data', p/'out', p/'ref'
    data.mkdir(); out.mkdir(); ref.mkdir()
    (data/'docs.txt').write_text(''.join(f'{i}\t'+' '.join(t for t,n in [('a',255),('b',257),('c',256)] if i<n)+'\n' for i in range(1025)))
    (data/'queries.txt').write_text('BOOL a OR c\nBOOL c AND c\nBOOL b NOT c\n')
    run = subprocess.run([str(binary)], env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)}, check=True, text=True, capture_output=True)
    lines = set(re.findall(r'PATH (\d+) (\d+) (sparse|dense)',run.stderr))
    assert {('0','511','sparse'),('1','512','sparse'),('2','513','dense')} <= lines, lines
    subprocess.run([sys.executable,str(ROOT/'official/reference/b_index.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
    assert (out/'results.txt').read_bytes()==(ref/'results.txt').read_bytes()

    # The full ID domain crosses every 64-bit word and worker chunk boundary.
    n = 250000
    a = {0,1,62,63,64,65,126,127,128,1023,1024,65535,65536,131071,131072,249990,249999}
    b = {1,63,64,126,128,1024,65535,131072,249990,249999}
    c = {0,62,64,127,128,65536,131071,249999}
    even = set(range(0,n,2))
    sets = {'a':a,'b':b,'c':c,'even':even,'missing':set()}
    queries = [
        [('OR','a')], [('OR','a'),('OR','b')], [('OR','a'),('AND','b')],
        [('OR','a'),('NOT','b')], [('OR','a'),('OR','b'),('AND','c')],
        [('OR','a'),('NOT','b'),('OR','c')], [('OR','a'),('AND','a')],
        [('OR','a'),('NOT','a')], [('OR','missing'),('OR','b')],
        [('OR','even'),('NOT','a')], [('OR','a'),('OR','even'),('AND','c')],
    ]
    with (data/'docs.txt').open('w') as f:
        for i in range(n):
            tokens = [name for name, values in sets.items() if name != 'missing' and i in values]
            f.write(f'{i}\t'+ ' '.join(tokens) + '\n')
    (data/'queries.txt').write_text(''.join('BOOL '+q[0][1]+''.join(f' {op} {term}' for op,term in q[1:])+'\n' for q in queries))
    expected=[]
    for q in queries:
        ids=set()
        for op,term in q:
            if op=='OR': ids |= sets[term]
            elif op=='AND': ids &= sets[term]
            else: ids -= sets[term]
        values=sorted(ids)
        expected.append(f'{len(values)} {sum(values)}'+''.join(f' {x}' for x in values[:10]))
    subprocess.run([str(binary)],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)},check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    assert (out/'results.txt').read_text().splitlines()==expected
    print('PASS exact 511/512/513 path selection and 250,000-document word/chunk boundaries')

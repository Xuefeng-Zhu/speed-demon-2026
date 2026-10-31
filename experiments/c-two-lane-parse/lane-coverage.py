#!/usr/bin/env python3
"""Instrument the exact C candidate and verify paired/tail coverage and output."""
import argparse
import hashlib
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXPECTED = '8249f318e26050cc1a12f2be091344bf431ceb862665a3312bb29a92e140057d'
p = argparse.ArgumentParser()
p.add_argument('--avx2', action='store_true')
args = p.parse_args()
source = (HERE / 'candidate.rs').read_text()
assert hashlib.sha256(source.encode()).hexdigest() == EXPECTED
def once(old, new):
    global source
    assert source.count(old) == 1, (old, source.count(old))
    source = source.replace(old, new, 1)

needle = 'let n = thread::available_parallelism().map_or(1, |n| n.get());'
once('let mut bins = vec![Vec::<Event>::new(); parts];',
     'let mut bins = vec![Vec::<Event>::new(); parts]; let mut seen=Vec::<i64>::new(); let mut paired=0usize; let mut tails=[0usize;2];')
once('while p0 < end0 && p1 < end1 {', 'while p0 < end0 && p1 < end1 { paired+=1;')
once('let id1 = positive_fast(recs, &mut p1);',
     'let id1 = positive_fast(recs, &mut p1); seen.push(id0); seen.push(id1);')
once('for (mut p, end) in [(p0, end0), (p1, end1)] {',
     'for (lane, (mut p, end)) in [(p0, end0), (p1, end1)].into_iter().enumerate() {')
once('while p < end {\n                    p +=', 'while p < end { tails[lane]+=1;\n                    p +=')
once('let id = positive_fast(recs, &mut p);\n                    let (name, name_len, h)',
     'let id = positive_fast(recs, &mut p); seen.push(id);\n                    let (name, name_len, h)')
once('(agg, bins)\n        });', '(agg, bins, seen, paired, tails)\n        });')
once('        let next = std::sync::atomic::AtomicUsize::new(0);',
     '''        let mut all=Vec::new(); let(mut pairs,mut t0,mut t1)=(0usize,0usize,0usize);
        for row in &parsed { all.extend_from_slice(&row.2); pairs+=row.3; t0+=row.4[0]; t1+=row.4[1]; }
        all.sort_unstable(); eprintln!("COV {} {} {} {:?}",pairs,t0,t1,all);
        let next = std::sync::atomic::AtomicUsize::new(0);''')

def row(i, name_len, terminal, bom):
    name = b'"N' + b'x' * name_len + b'"'
    # Quoted LF is part of the value; doubled quotes and comma remain hostile.
    note = b'"alpha\nbeta, ""q"""'
    return (b'\xef\xbb\xbf' if bom else b'') + str(i).encode() + b',' + name + b',' + note + b',1,-0.05' + terminal

workers=(1,2,3,7,12)
flags=['-C','target-cpu=x86-64-v3'] if args.avx2 else []
coverage={'paired':0,'tail0':0,'tail1':0,'collapsed':0,'bom':0,'embedded_lf':0,'long':0,'long_cross':0}
checks=0
with tempfile.TemporaryDirectory(prefix='c-two-lane-coverage-') as td:
    root=Path(td); bins={}
    for n in workers:
        assert source.count(needle)==1
        path=root / f'candidate-{n}.rs'; exe=root / f'candidate-{n}'
        path.write_text(source.replace(needle, f'let n = {n};'))
        subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',*flags,str(path),'-o',str(exe)],check=True)
        bins[n]=exe
    for case in range(14):
        rng=random.Random(9315+case)
        case_dir=root / f'case-{case}';data=case_dir/'data';ref=case_dir/'ref'
        data.mkdir(parents=True);ref.mkdir()
        (data/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n')
        count = 1 if case == 0 else (1200 if case in (1,2) else 40 + case*9)
        rows=[]
        for i in range(1,count+1):
            if case == 0: size=100000
            elif case == 1: size=3 if i <= count*9//10 else 420
            elif case == 2: size=420 if i <= count//10 else 3
            elif case == 3 and i==count//2: size=80000
            else: size=rng.randrange(0,80)
            term=b'\r\n' if i==count or (case not in (0,4) and i%7==0) else b'\n'
            rows.append(row(i,size,term,i>1 and i%11==0))
        header=b'\xef\xbb\xbfid,name,note,region_id,amount\r\n';raw=header+b''.join(rows)
        (data/'records.csv').write_bytes(raw)
        subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
        expected=(ref/'aggregates.txt').read_bytes()
        if b'\xef\xbb\xbf' in b''.join(rows): coverage['bom']+=1
        if b'alpha\nbeta' in raw: coverage['embedded_lf']+=1
        if max(map(len,rows)) > 65535: coverage['long']+=1
        for n in workers:
            starts=[]
            for i in range(1,2*n):
                at=len(header)+(len(raw)-len(header))*i//(2*n)
                cr=raw.find(b'\r',at); starts.append(len(raw) if cr<0 else cr+2)
            if len(starts)!=len(set(starts)): coverage['collapsed']+=1
            if case==0 and n>1 and len(starts)>1 and all(v==len(raw) for v in starts): coverage['long_cross']+=1
            out=case_dir / f'out-{n}';out.mkdir()
            run=subprocess.run([str(bins[n])],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),capture_output=True,check=True,text=True)
            assert (out/'aggregates.txt').read_bytes()==expected,(case,n,'output')
            match=re.search(r'^COV (\d+) (\d+) (\d+) \[([^\]]*)\]$',run.stderr,re.M)
            assert match,(case,n,run.stderr[-1000:])
            pair,tail0,tail1=map(int,match.group(1,2,3));raw_ids=match.group(4).strip()
            ids=[] if not raw_ids else [int(v) for v in raw_ids.split(',')]
            assert ids==list(range(1,count+1)),(case,n,'missing or duplicated ids')
            coverage['paired']+=bool(pair);coverage['tail0']+=bool(tail0);coverage['tail1']+=bool(tail1)
            checks+=1
assert all(coverage.values()),coverage
print('PASS',checks,'exact-source lane-coverage/reference cases',coverage)

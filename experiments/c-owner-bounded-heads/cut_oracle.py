#!/usr/bin/env python3
import os, random, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT/'experiments/c-owner-bounded-heads/candidate.rs').read_text()
needle = 'let n = thread::available_parallelism().map_or(1, |n| n.get());'
assert source.count(needle) == 1
threads = (1, 2, 3, 7, 12, 32, 64)
with tempfile.TemporaryDirectory(prefix='c-crlf-cut-') as tmp:
    root = Path(tmp)
    for n in threads:
        src = root / f'c{n}.rs'
        src.write_text(source.replace(needle, f'let n = {n};'))
        subprocess.run(['rustc','--edition=2021','-O'] + (['-C','target-cpu=x86-64-v3'] if '--avx2' in sys.argv else []) + [str(src),'-o',str(root / f'c{n}')],check=True)
    categories = {'at_cr':0, 'at_lf_after_cr':0, 'bare_lf':0, 'same_cut':0}
    total=0
    for case in range(51):
        rng = random.Random(700 + case)
        dir = root / f'case{case}';data=dir/'data';ref=dir/'ref';data.mkdir(parents=True);ref.mkdir()
        (data/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n2,BBB\n')
        header = b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'
        count = 1 if case == 0 else (2200 if case == 50 else 9+case*3)
        rows=[]
        for i in range(count):
            # Several initial long LF-only records force boundaries to collapse at the last CRLF.
            name=('"A' + ('x'*(120000 if case == 49 and i == count//2 else rng.randrange(0,65))) + '"').encode()
            note=(b'"a\nb\nc\nd"' if i%3==0 else b'"said ""no"" twice"')
            bom = b'\xef\xbb\xbf' if i>0 and i%11==0 else b''
            term = b'\r\n' if i==count-1 or (case not in (0,50) and i%5==0) else b'\n'
            rows.append(bom + str(i+1).encode() + b','+name+b','+note+b','+str(1+i%2).encode()+b',-0.05'+term)
        raw=header+b''.join(rows);(data/'records.csv').write_bytes(raw)
        subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
        expected=(ref/'aggregates.txt').read_bytes(); start=len(header)
        for n in threads:
            cuts=[start+(len(raw)-start)*t//n for t in range(1,n)]
            bounds=[]
            for p in cuts:
                if p<len(raw) and raw[p:p+2]==b'\r\n': categories['at_cr']+=1
                if p<len(raw) and p>0 and raw[p:p+1]==b'\n' and raw[p-1:p]==b'\r': categories['at_lf_after_cr']+=1
                if p<len(raw) and raw[p:p+1]==b'\n' and (p==0 or raw[p-1:p]!=b'\r'): categories['bare_lf']+=1
                pos=raw.find(b'\r',p); bounds.append(len(raw) if pos<0 else pos+2)
            if len(bounds)>len(set(bounds)): categories['same_cut']+=1
            out=dir/f'out{n}';out.mkdir()
            subprocess.run([str(root/f'c{n}')],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True,stdout=subprocess.DEVNULL)
            if (out/'aggregates.txt').read_bytes()!=expected: raise SystemExit(f'FAIL case={case} workers={n}')
            total+=1
    print('PASS', total, 'reference comparisons; cut coverage', categories)
    assert all(categories.values()), categories

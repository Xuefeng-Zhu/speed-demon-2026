#!/usr/bin/env python3
"""Force all three packed parser hash sites to collide and verify promotion."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
EXPECTED='b82a3f980ee59aa72c6cd01c42b096deccd4476bc4a32c116786361705ab8471'
p=argparse.ArgumentParser();p.add_argument('--avx2',action='store_true');a=p.parse_args()
s=(HERE/'candidate.rs').read_text();assert hashlib.sha256(s.encode()).hexdigest()==EXPECTED
for suffix in ('0','1',''):
    x='p'+suffix
    old=f'let (name{suffix}, name_len{suffix}, h{suffix}) = field_name_hash(recs, &mut {x});'
    new=f'let (name{suffix}, name_len{suffix}, _h{suffix}) = field_name_hash(recs, &mut {x}); let h{suffix}=0u64;'
    assert s.count(old)==1,old;s=s.replace(old,new,1)
assert s.count('if count >= 8 {')==1
s=s.replace('if count >= 8 {','if count >= 8 { eprintln!("FORCED_PROMOTION");',1)
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());';assert s.count(needle)==1
def letters(i):
    result=''
    for _ in range(4): result=chr(65+i%26)+result;i//=26
    return result
def quote(value): return '"'+value.replace('"','""')+'"'
flags=['-C','target-cpu=x86-64-v3'] if a.avx2 else []
with tempfile.TemporaryDirectory(prefix='c-two-lane-collision-') as td:
    root=Path(td);data=root/'data';ref=root/'ref';data.mkdir();ref.mkdir()
    (data/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n2,BBB\n')
    rows=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
    for i in range(1,2401):
        key=(i-1)%600
        name='Name '+letters(key)
        if key%19==0: name+=', "quoted"'
        if key%23==0: name+=' '
        if i==700: name='Long '+('z'*70000)
        if i==701: name=''
        note='a\nb, "c"'
        bom=b'\xef\xbb\xbf' if i%101==0 else b''
        term=b'\r\n' if i%7==0 or i==2400 else b'\n'
        rows.append(bom+f'{i},{quote(name)},{quote(note)},{1+i%2},1.25'.encode()+term)
    (data/'records.csv').write_bytes(b''.join(rows))
    subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
    expected=(ref/'aggregates.txt').read_bytes()
    for n in (1,2,3,7,12):
        path=root/f'candidate-{n}.rs';exe=root/f'candidate-{n}';out=root/f'out-{n}';out.mkdir()
        path.write_text(s.replace(needle,f'let n = {n};'))
        subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',*flags,str(path),'-o',str(exe)],check=True)
        run=subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),capture_output=True,check=True,text=True)
        assert (out/'aggregates.txt').read_bytes()==expected,(n,'output')
        assert 'FORCED_PROMOTION' in run.stderr,(n,'promotion not exercised')
print('PASS exact three-site forced collision, promotion and sentinel across 5 worker counts')

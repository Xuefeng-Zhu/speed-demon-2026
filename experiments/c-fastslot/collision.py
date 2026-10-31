#!/usr/bin/env python3
"""Exercise the >256-group fallback and total name-hash collisions against reference."""
import os, random, subprocess, tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[2]
src = (root/'experiments/c-fastslot/candidate.rs').read_text()
needle = 'let n = thread::available_parallelism().map_or(1, |n| n.get());'
assert src.count(needle) == 1
old = 'self.0 ^ self.0 >> 29'
assert src.count(old) == 1
with tempfile.TemporaryDirectory(prefix='c-inline-collision-') as tmp:
    d=Path(tmp); data=d/'data'; ref=d/'ref'; data.mkdir(); ref.mkdir()
    codes=[chr(65+i//676)+chr(65+(i//26)%26)+chr(65+i%26) for i in range(310)]
    (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},{c}\n' for i,c in enumerate(codes)))
    rng=random.Random(371); rows=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
    names=['', 'A', 'A ', 'A, B', 'A "B"']+[f'Person {i}' for i in range(75)]
    quote=lambda v:'"'+v.replace('"','""')+'"'
    for i in range(1,2501):
        name=rng.choice(names); note=rng.choice(['', 'line\nline', 'said "no"', 'abc, def'])
        region=(i if i<=310 else rng.randrange(1, 312))
        row=f'{i},{quote(name)},{quote(note)},{region},{rng.choice(["0.00", "-0.01", "99999.99"])}'
        rows.append(row.encode()+(b'\r\n' if i==2500 or i%3==0 else b'\n'))
    (data/'records.csv').write_bytes(b''.join(rows))
    subprocess.run(['python3',str(root/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True)
    expected=(ref/'aggregates.txt').read_bytes()
    for collision in (False,True):
        s=src.replace(old,'0') if collision else src
        for n in (1,2,7,16):
            path=d/f'src-{collision}-{n}.rs';binary=d/f'bin-{collision}-{n}'
            path.write_text(s.replace(needle,f'let n = {n};'))
            subprocess.run(['rustc','--edition=2021','-O',str(path),'-o',str(binary)],check=True)
            out=d/f'out-{collision}-{n}';out.mkdir()
            subprocess.run([str(binary)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True)
            assert (out/'aggregates.txt').read_bytes()==expected,(collision,n)
print('PASS: 310-country, normal and forced-constant hash, four worker counts')

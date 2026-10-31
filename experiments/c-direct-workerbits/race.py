#!/usr/bin/env python3
"""Race first insertion and group bits, with forced hash collisions, against the reference."""
import os, subprocess, tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[2]
src = (root/'experiments/c-direct-workerbits/candidate.rs').read_text()
needle = 'let n = thread::available_parallelism().map_or(1, |n| n.get());'
hashneedle = 'let (name,name_len,h) = field_name_hash(recs, &mut p);'
assert src.count(needle) == 1 and src.count(hashneedle) == 1
with tempfile.TemporaryDirectory(prefix='c-fastslot-race-') as tmp:
    d=Path(tmp); data=d/'data'; ref=d/'ref'; data.mkdir(); ref.mkdir()
    codes=[chr(65+i//676)+chr(65+(i//26)%26)+chr(65+i%26) for i in range(255)]
    (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},{c}\n' for i,c in enumerate(codes)))
    rows=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
    names=['', '""', '"A"', '"A, B"', '"A ""B"""', '"same"']
    for i in range(1,32769):
        # Repeated identical names and alternating different names make workers
        # race at initial publication and at multiple 64-bit group boundaries.
        name=names[(i * 131 // 257) % len(names)]
        region=1 + (i * 313 % 255)
        rows.append(f'{i},{name},"x",{region},1.25\r\n'.encode())
    (data/'records.csv').write_bytes(b''.join(rows))
    subprocess.run(['python3',str(root/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True)
    expected=(ref/'aggregates.txt').read_bytes()
    count=0
    for force in ("normal", "constant", "single_slot"):
        for n in (2, 8, 32):
            source=(src.replace(hashneedle, hashneedle + ' let h=0u64;') if force == 'constant' else src).replace(needle, f'let n = {n};')
            if force == 'single_slot':
                assert source.count('(1 << 20)') == 1
                source=source.replace('(1 << 20)', '(1 << 0)')
            path=d/f'src-{force}-{n}.rs'; exe=d/f'bin-{force}-{n}'; path.write_text(source)
            subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(path),'-o',str(exe)],check=True)
            out=d/f'out-{force}-{n}';out.mkdir()
            for rep in range(3):
                subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True)
                assert (out/'aggregates.txt').read_bytes()==expected,(force,n,rep)
                count+=1
print(f'PASS: {count} concurrent reference runs across 255 groups, escaped and empty names, normal, forced-constant hash, and one-slot cache')

#!/usr/bin/env python3
"""Construct exact nine-way split offsets around a line boundary."""
import subprocess,sys,tempfile,hashlib
from pathlib import Path
REFERENCE=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else (Path.cwd()/'official/reference/b_index.py').resolve()
binary=Path(sys.argv[1]).resolve(); qs='PHRASE "a b"\nPHRASE "a a"\nBOOL a NOT b OR c\nBOOL x OR z\n'
digests=[]
with tempfile.TemporaryDirectory(prefix='b-byte-exact-') as td:
 root=Path(td)
 for delta in range(-16,17):
  # The file is exactly 3600 bytes, putting the first raw cut at 400.
  # Move the first line's end across it; delta=0 is exactly a line start,
  # delta=1 points exactly at LF, delta<0 falls in the second line.
  lens=[400+delta]+[400]*7+[400-delta]
  docs=b''.join(str(i).encode()+b'\t'+b'a a b c x'+b'.'*(length-12)+b'\n' for i,length in enumerate(lens))
  assert len(docs)==3600 and all(length>=12 for length in lens)
  data=root/f'data{delta}';ref=root/f'ref{delta}';out=root/f'out{delta}'
  for p in (data,ref,out):p.mkdir()
  (data/'docs.txt').write_bytes(docs);(data/'queries.txt').write_text(qs)
  subprocess.run([sys.executable,str(REFERENCE),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([str(binary),str(data/'docs.txt'),str(data/'queries.txt'),str(out/'results.txt')],check=True,stdout=subprocess.DEVNULL)
  got=(out/'results.txt').read_bytes(); assert got==(ref/'results.txt').read_bytes(),delta
  digests.append(hashlib.sha256(got).hexdigest())
print('PASS 33 exact-byte-cut cases, including line start, LF and 16 bytes on either side; aggregate',hashlib.sha256(''.join(digests).encode()).hexdigest())

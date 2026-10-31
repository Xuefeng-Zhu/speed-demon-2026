#!/usr/bin/env python3
import subprocess,sys,tempfile
from pathlib import Path
exe=sys.argv[1]; ref=sys.argv[2]; bom=b'\xef\xbb\xbf'
with tempfile.TemporaryDirectory(prefix='c-mmap-edge-') as d:
 root=Path(d);data=root/'data';refout=root/'ref';out=root/'out'
 for x in (data,refout,out):x.mkdir()
 (data/'regions.csv').write_bytes(b'region_id,country\n1,USA\n')
 header=bom+b'id,name,note,region_id,amount\r\n'
 def check(label,records):
  (data/'records.csv').write_bytes(records)
  subprocess.run([sys.executable,ref,'--data',str(data),'--out',str(refout)],check=True)
  subprocess.run([exe,str(data),str(out)],check=True)
  assert (refout/'aggregates.txt').read_bytes()==(out/'aggregates.txt').read_bytes(), label
  print('PASS',label,flush=True)
 check('header-only',header)
 check('first row LF + second BOM CRLF',header+b'1,"Alice","x",1,0.00\n'+bom+b'2,"Bob","say ""hi""\nthere",1,-0.01\r\n')
 check('final LF',header+b'1,"Alice","x",1,0.00\n')
 check('final CRLF',header+b'1,"Alice","x",1,0.00\r\n')
 check('final no terminator',header+b'1,"Alice","x",1,0.00')
 prefix=header+b'1,"Alice","'; suffix=b'",1,0.00'; pad=4096-len(prefix)-len(suffix)
 assert pad>0
 page=prefix+b'a'*pad+suffix
 assert len(page)==4096
 check('unterminated file ends at mapping page boundary',page)

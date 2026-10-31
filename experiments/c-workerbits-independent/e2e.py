#!/usr/bin/env python3
"""Independent forced-slot collision and 256/257 group + worker gate comparison."""
import csv, hashlib, os, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=(ROOT/'experiments/c-direct-workerbits/candidate.rs').read_text()
assert hashlib.sha256(s.encode()).hexdigest()=='f2b9e6bc60da6fd12778580bd7cc9371b21a269f49758df76f07af82894c2164'
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());';assert s.count(needle)==1
s=s.replace(needle,'let n = std::env::var("SD_TEST_WORKERS").unwrap().parse::<usize>().unwrap();')
direct='''if can_pack(recs.len(), unmatched) && words <= 4 && n <= 16 {'''
owner='''} else if can_pack(recs.len(), unmatched) {'''
large='''    } else {
        let names: Vec<Shard>'''
for a in (direct,owner,large): assert s.count(a)==1
s=s.replace(direct,direct+' eprintln!("DIRECT");').replace(owner,owner+' eprintln!("OWNER");').replace(large,'''    } else {
        eprintln!("LARGE");
        let names: Vec<Shard>''')
needle='let (name,name_len,h) = field_name_hash(recs, &mut p);';assert s.count(needle)==1
variants={'normal':s,'same_slot':s.replace(needle,'let (name,name_len,_h) = field_name_hash(recs, &mut p); let h = 0u64;'),'large':s.replace('const MAX_PACKED_FILE: usize = u32::MAX as usize;','const MAX_PACKED_FILE: usize = 1;')}
def code(i):return ''.join(chr(65+(i//k)%26) for k in (676,26,1))
with tempfile.TemporaryDirectory(prefix='workerbits-e2e-') as td:
 root=Path(td); bins={}
 for label,body in variants.items():
  src=root/(label+'.rs');exe=root/label;src.write_text(body)
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True,timeout=60)
  bins[label]=exe
 for ngroup in [256,257]:
  data=root/f'data{ngroup}';ref=root/f'ref{ngroup}';data.mkdir();ref.mkdir()
  (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},{code(i)}\n' for i in range(ngroup-1)))
  with (data/'records.csv').open('w',newline='') as f:
   f.write('\ufeffid,name,note,region_id,amount\r\n');w=csv.writer(f,lineterminator='\r\n',quoting=csv.QUOTE_NONNUMERIC)
   for i in range(1,5001):
    name=['', 'A', 'A ', 'A"B', 'B,C', 'z'*65537][i%6]
    # Unknown region exercises unmatched as final group; all names span groups.
    rid=9999999 if i%ngroup==0 else (i%ngroup)+1
    # Hand formatting ensures numeric fields unquoted under §2.2.
    q='"'+name.replace('"','""')+'"' if name or i%2 else ''
    f.write(f'{i},{q},"x\ny",{rid},-1.25\r\n')
  subprocess.run([sys.executable,'-c','import csv,runpy,sys;csv.field_size_limit(10000000);sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name="__main__")',str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL,timeout=60)
  expected=(ref/'aggregates.txt').read_bytes()
  for label in variants:
   for n in (2,7,16,17):
    out=root/f'out-{ngroup}-{label}-{n}';out.mkdir()
    p=subprocess.run([str(bins[label])],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_TEST_WORKERS=str(n)),capture_output=True,check=True,timeout=90)
    branch='LARGE' if label=='large' else ('DIRECT' if ngroup==256 and n<=16 else 'OWNER')
    assert branch.encode() in p.stderr,(ngroup,label,n,p.stderr)
    assert (out/'aggregates.txt').read_bytes()==expected,(ngroup,label,n)
    print('PASS',ngroup,label,n,branch,flush=True)

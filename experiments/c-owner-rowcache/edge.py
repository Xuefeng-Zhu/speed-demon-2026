#!/usr/bin/env python3
"""End-to-end sentinel, owner, collision, and forced fallback reference tests."""
import os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
s=(HERE/'candidate.rs').read_text()
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
branch='if can_pack(recs.len(), unmatched) {'
fall='''    } else {
        let names: Vec<Shard>'''
sentinel='''    if event.len != u16::MAX { return &recs[start..start + event.len as usize]; }'''
route='let h = BuildHasherDefault::<Fx>::default().hash_one(name);'
finish='self.0 ^ self.0 >> 29'
for x in (needle,branch,fall,sentinel,route,finish): assert s.count(x)==1, x
s=s.replace(needle,'let n = std::env::var("SD_TEST_WORKERS").unwrap().parse::<usize>().unwrap();')
s=s.replace(branch,branch+' eprintln!("PACKED_BRANCH");').replace(fall,'''    } else {
        eprintln!("FALLBACK_BRANCH");
        let names: Vec<Shard>''').replace(sentinel,sentinel+' eprintln!("LONG_NAME");')
variants={'normal':s,'collision':s.replace(route,'let h = 0u64;'),'fullhash_collision':s.replace(finish,'0'),
          'large_file_fallback':s.replace('const MAX_PACKED_FILE: usize = u32::MAX as usize;','const MAX_PACKED_FILE: usize = 1;'),
          'many_groups_fallback':s.replace('const MAX_PACKED_GROUPS: usize = u16::MAX as usize;','const MAX_PACKED_GROUPS: usize = 1;')}
with tempfile.TemporaryDirectory(prefix='c-compact-edge-') as td:
 root=Path(td);data=root/'data';ref=root/'ref';data.mkdir();ref.mkdir();bins={}
 for name,text in variants.items():
  src=root/f'{name}.rs';exe=root/name;src.write_text(text)
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes'] + (['-C','target-cpu=x86-64-v3'] if '--avx2' in sys.argv else []) + [str(src),'-o',str(exe)],check=True);bins[name]=exe
 (data/'regions.csv').write_text('region_id,country\n1,AAA\n2,BBB\n999999,AAA\n')
 names=['', 'A'*65534, 'B'*65535, 'C'*65536, 'D'*65535+'"Q"'+'D'*65536, 'A'*65533+' ', 'short', 'short ']
 rows=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'];i=0
 for repeat in range(3):
  for j,name in enumerate(names):
   i+=1;enc='"'+name.replace('"','""')+'"' if name or repeat%2 else ''
   reg=[1,2,9999999][(j+repeat)%3];amount=['0.00','-0.05','99999.99'][i%3]
   bom=b'\xef\xbb\xbf' if i>1 and i%7==0 else b'';eol=b'\r\n' if i%2==0 or (repeat==2 and j==len(names)-1) else b'\n'
   rows.append(bom+f'{i},{enc},"a\nb",{reg},{amount}'.encode()+eol)
 (data/'records.csv').write_bytes(b''.join(rows))
 subprocess.run([sys.executable,'-c','import csv,runpy,sys;csv.field_size_limit(10000000);sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name="__main__")',str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
 expected=(ref/'aggregates.txt').read_bytes(); count=0
 for name,exe in bins.items():
  for workers in (1,2,7,32):
   out=root/f'out-{name}-{workers}';out.mkdir()
   p=subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_TEST_WORKERS=str(workers)),capture_output=True,text=True,check=True,timeout=90)
   assert (out/'aggregates.txt').read_bytes()==expected,(name,workers)
   if name in ('normal','collision','fullhash_collision'):
    assert 'PACKED_BRANCH' in p.stderr and 'LONG_NAME' in p.stderr,(name,workers,p.stderr[:300])
   else: assert 'FALLBACK_BRANCH' in p.stderr and 'LONG_NAME' not in p.stderr,(name,workers,p.stderr[:300])
   count+=1
 print(f'PASS {count} long-name/sentinel, forced routing collision and pre-output fallback reference comparisons')

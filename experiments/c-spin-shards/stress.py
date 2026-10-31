#!/usr/bin/env python3
"""Full-program exact-reference contention and collision stress, no external data."""
import hashlib,json,os,random,statistics,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
THREADS=[1,2,7,32]
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
shard='let shard = BuildHasherDefault::<Fx>::default().hash_one(name) >> 32 & 1023;'
hashfinish='self.0 ^ self.0 >> 29'
rng=random.Random(81301)
report={}
with tempfile.TemporaryDirectory(prefix='c-spin-stress-') as tmp:
 p=Path(tmp); data=p/'data';ref=p/'ref';out=p/'out';data.mkdir();ref.mkdir();out.mkdir()
 (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},AA{chr(65+i)}\n' for i in range(8)))
 bins={}
 for hash_mode in ('shard','collision'):
  for label in ('baseline','candidate'):
   s=(HERE/(label+'.rs')).read_text();assert s.count(needle)==1 and s.count(shard)==1 and s.count(hashfinish)==1
   s=s.replace(needle,'let n = std::env::var("SD_TEST_WORKERS").unwrap().parse::<usize>().unwrap();').replace(shard,'let shard = 0usize;')
   if hash_mode=='collision':s=s.replace(hashfinish,'0')
   src=p/f'{label}-{hash_mode}.rs';exe=p/f'{label}-{hash_mode}';src.write_text(s)
   subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True)
   bins[(label,hash_mode)]=exe
 for dataset in ('one_name','many_names'):
  rows=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
  for i in range(1,20_001):
   name='constant' if dataset=='one_name' else f'Name-{i%257:03d}'
   rows.append(f'{i},"{name}","x",{1+i%8},{"-0.05" if i%9==0 else "1.25"}\r\n'.encode())
  (data/'records.csv').write_bytes(b''.join(rows))
  subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
  expected=(ref/'aggregates.txt').read_bytes()
  for hash_mode in ('shard','collision'):
   for workers in THREADS:
    runs={'baseline':[],'candidate':[]}
    for _ in range(3):
     order=['baseline','candidate'];rng.shuffle(order)
     for label in order:
      result=out/'aggregates.txt';result.unlink(missing_ok=True)
      env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_TEST_WORKERS=str(workers))
      t=time.perf_counter();subprocess.run([str(bins[(label,hash_mode)])],env=env,check=True,timeout=45,stdout=subprocess.DEVNULL); elapsed=time.perf_counter()-t
      if result.read_bytes()!=expected:raise SystemExit(f'mismatch: {dataset} {hash_mode} {workers} {label}')
      runs[label].append(elapsed)
    key=f'{dataset}/{hash_mode}/{workers}';report[key]=runs
    print(key, 'baseline',round(statistics.median(runs['baseline']),5),'candidate',round(statistics.median(runs['candidate']),5),flush=True)
 Path('experiments/c-spin-shards/stress-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS',len(report)*6,'exact reference executions',flush=True)

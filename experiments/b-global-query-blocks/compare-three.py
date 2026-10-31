#!/usr/bin/env python3
"""Serial three-way full-hash or reordered-query differential benchmark."""
import argparse,hashlib,json,os,random,statistics,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ('original','shared','dynamic'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--data',type=Path,required=True);p.add_argument('--query-file',type=Path,help='independently generated reordered queries; differential only');p.add_argument('--sort-syntax',action='store_true',help='sort query rows by syntactic type/length; differential only');p.add_argument('--runs',type=int,default=15);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
if a.runs<1:p.error('runs must be positive')
bins={n:str(getattr(a,n).resolve(strict=True)) for n in ('original','shared','dynamic')};origin=a.data.resolve(strict=True);query=(a.query_file.resolve(strict=True) if a.query_file else origin/'queries.txt');results={n:[] for n in bins}
with tempfile.TemporaryDirectory(prefix='b-three-query-') as d:
 root=Path(d);data=root/'data';out=root/'out';data.mkdir();out.mkdir();(data/'docs.txt').symlink_to(origin/'docs.txt')
 q=query.read_bytes()
 if a.sort_syntax:
  rows=q.splitlines();rows.sort(key=lambda line:(line.startswith(b'PHRASE '),line.count(b' '),line));q=b'\n'.join(rows)+(b'\n' if rows else b'')
 (data/'queries.txt').write_bytes(q)
 env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)};subprocess.run([bins['original']],env=env,check=True);expected=hashlib.sha256((out/'results.txt').read_bytes()).hexdigest()
 if not a.query_file and not a.sort_syntax:
  assert expected=='f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927','original binary did not match official full seed 1 hash'
 for i in range(a.runs+1):
  order=list(bins);random.Random(72499+i).shuffle(order)
  for name in order:
   start=time.perf_counter();proc=subprocess.Popen([bins[name]],env=env);_,status,u=os.wait4(proc.pid,0);wall=time.perf_counter()-start
   assert os.waitstatus_to_exitcode(status)==0,(name,i,status)
   assert hashlib.sha256((out/'results.txt').read_bytes()).hexdigest()==expected,(name,i,'output mismatch')
   results[name].append({'wall_s':wall,'cpu_s':u.ru_utime+u.ru_stime,'max_rss_native':u.ru_maxrss,'warmup':i==0})
for name,rows in results.items():
 measured=[x for x in rows if not x['warmup']];print(name,'median wall',statistics.median(x['wall_s'] for x in measured),'median CPU',statistics.median(x['cpu_s'] for x in measured),'max native RSS',max(x['max_rss_native'] for x in measured))
a.report.write_text(json.dumps({'comparison':'official hash' if not a.query_file and not a.sort_syntax else 'runtime-generated differential, not official hash','results':results},indent=2)+'\n')

#!/usr/bin/env python3
"""Reorder supplied queries syntactically to probe scheduling, never cache answers."""
import argparse,hashlib,json,os,random,statistics,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--runs',type=int,default=9);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
assert a.runs>0
bins={'baseline':str(a.baseline.resolve(strict=True)),'candidate':str(a.candidate.resolve(strict=True))};origin=a.data.resolve(strict=True);result={x:[] for x in bins}
with tempfile.TemporaryDirectory(prefix='b-query-skew-') as d:
 root=Path(d);data=root/'data';out=root/'out';data.mkdir();out.mkdir();(data/'docs.txt').symlink_to(origin/'docs.txt')
 queries=(origin/'queries.txt').read_bytes().splitlines();queries.sort(key=lambda q:(q.startswith(b'PHRASE '),q.count(b' '),q))
 (data/'queries.txt').write_bytes(b'\n'.join(queries)+b'\n')
 env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)}; subprocess.run([bins['baseline']],env=env,check=True);expected=hashlib.sha256((out/'results.txt').read_bytes()).hexdigest()
 for i in range(a.runs+1):
  order=list(bins);random.Random(4931+i).shuffle(order)
  for name in order:
   start=time.perf_counter();proc=subprocess.Popen([bins[name]],env=env);_,status,u=os.wait4(proc.pid,0);wall=time.perf_counter()-start
   assert os.waitstatus_to_exitcode(status)==0 and hashlib.sha256((out/'results.txt').read_bytes()).hexdigest()==expected,(name,i)
   result[name].append({'wall_s':wall,'cpu_s':u.ru_utime+u.ru_stime,'max_rss_native':u.ru_maxrss,'warmup':i==0})
for name,rows in result.items():
 measured=[x for x in rows if not x['warmup']];print(name,'wall',statistics.median(x['wall_s'] for x in measured),'cpu',statistics.median(x['cpu_s'] for x in measured))
a.report.write_text(json.dumps({'description':'sorted-query differential only, native process metrics','results':result},indent=2)+'\n')

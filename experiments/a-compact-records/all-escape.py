#!/usr/bin/env python3
"""Generate/dispose 3.1M all-escape records; native RSS is not cgroup peak."""
import argparse, json, os, random, statistics, subprocess, tempfile, time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',required=True);p.add_argument('--candidate',required=True);p.add_argument('--report',required=True);p.add_argument('--runs',type=int,default=3);args=p.parse_args()
assert args.runs>=1
with tempfile.TemporaryDirectory(prefix='a-all-escape-') as t:
 root=Path(t);data=root/'data';out=root/'out';data.mkdir();out.mkdir();line=b'2026-10-30T18:00:00.000000Z GET / 599 4294967295\n';n=3_100_000;chunk=line*8192
 with (data/'requests.log').open('wb') as f:
  for _ in range(n//8192):f.write(chunk)
  f.write(line*(n%8192))
 want=b'2026-10-30T18:00:00Z / 3100000 4294967295 4294967295 4294967295 3100000 1000000\n'
 result={}
 for workers in [1,12]:
  result[str(workers)]={'baseline':[],'candidate':[]};env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out),'SD_THREADS':str(workers)}
  for i in range(args.runs+1):
   names=['baseline','candidate'];random.Random(398+i).shuffle(names)
   for name in names:
    start=time.perf_counter();proc=subprocess.Popen([str(Path(getattr(args,name)).resolve())],env=env);_,status,u=os.wait4(proc.pid,0);elapsed=time.perf_counter()-start
    assert os.waitstatus_to_exitcode(status)==0 and (out/'summary.txt').read_bytes()==want,(workers,name,i)
    result[str(workers)][name].append({'wall_s':elapsed,'cpu_s':u.ru_utime+u.ru_stime,'rss_native':u.ru_maxrss,'warmup':i==0})
for workers,groups in result.items():
 for name,rows in groups.items():
  print(workers,name,'median wall',statistics.median(x['wall_s'] for x in rows[1:]),'max native RSS',max(x['rss_native'] for x in rows[1:]))
Path(args.report).write_text(json.dumps(result,indent=2)+'\n')

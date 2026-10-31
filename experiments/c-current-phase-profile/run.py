#!/usr/bin/env python3
"""Instrumented phase timings; not a production benchmark."""
import hashlib, json, os, pathlib, statistics, subprocess, tempfile, sys
binary,data=map(pathlib.Path,sys.argv[1:3]); binary=binary.resolve(); data=data.resolve()
expected='d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536'
reports=[]
with tempfile.TemporaryDirectory() as out:
 for i in range(11):
  env=os.environ|{'SD_DATA':str(data),'SD_OUT':out}
  p=subprocess.run([binary],env=env,capture_output=True,text=True,check=True)
  actual=hashlib.sha256((pathlib.Path(out)/'aggregates.txt').read_bytes()).hexdigest()
  assert actual==expected,(i,actual)
  m={}
  for line in p.stderr.splitlines():
   parts=line.split()
   if parts[:1]==['PROFILE']:
    key=parts[1]; m.setdefault(key,[]).append(float(parts[-1]))
  assert set(m)=={'setup','parse_wall','parse_worker','reduce_wall','reduce_worker','total'},m
  if i: reports.append(m)
summary={k:statistics.median(x[k][0] for x in reports) for k in ['setup','parse_wall','reduce_wall','total']}
summary.update({k+'_median_worker':statistics.median(v for x in reports for v in x[k]) for k in ['parse_worker','reduce_worker']})
summary.update({k+'_median_maxworker':statistics.median(max(x[k]) for x in reports) for k in ['parse_worker','reduce_worker']})
summary.update({k+'_median_sumworker':statistics.median(sum(x[k]) for x in reports) for k in ['parse_worker','reduce_worker']})
print(json.dumps({'summary':summary,'samples':reports},indent=2))

#!/usr/bin/env python3
"""Alternating instrumented diagnostic phase timings, not production benchmark."""
import hashlib,json,os,pathlib,random,statistics,subprocess,sys,tempfile
binaries={'baseline':str(pathlib.Path(sys.argv[1]).resolve()),'candidate':str(pathlib.Path(sys.argv[2]).resolve())}
data=str(pathlib.Path(sys.argv[3]).resolve()); expected='d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536'; results={k:[] for k in binaries};rng=random.Random(818)
with tempfile.TemporaryDirectory() as out:
 for i in range(16):
  order=list(binaries);rng.shuffle(order)
  for label in order:
   p=subprocess.run([binaries[label]],env=os.environ|{'SD_DATA':data,'SD_OUT':out},capture_output=True,text=True,check=True)
   assert hashlib.sha256((pathlib.Path(out)/'aggregates.txt').read_bytes()).hexdigest()==expected
   m={}
   for line in p.stderr.splitlines():
    parts=line.split()
    if parts[:1]==['PROFILE']:m.setdefault(parts[1],[]).append(float(parts[-1]))
   assert set(m)=={'setup','parse_wall','parse_worker','reduce_wall','reduce_worker','total'}
   if i:results[label].append(m)
summary={label:{k:statistics.median(r[k][0] for r in rows) for k in ('setup','parse_wall','reduce_wall','total')} for label,rows in results.items()}
print(json.dumps({'summary':summary,'samples':results},indent=2))

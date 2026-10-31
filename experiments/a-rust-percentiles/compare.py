#!/usr/bin/env python3
"""Compare two Rust A binaries in randomized order against a known output hash."""
import argparse, hashlib, json, os, pathlib, random, statistics, subprocess, tempfile, time
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',required=True,type=pathlib.Path); p.add_argument('--candidate',required=True,type=pathlib.Path)
p.add_argument('--data',required=True,type=pathlib.Path); p.add_argument('--report',required=True,type=pathlib.Path)
p.add_argument('--runs',default=15,type=int); p.add_argument('--threads',default=12,type=int)
p.add_argument('--expected',default='495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3')
a=p.parse_args(); bins={'baseline':a.baseline.resolve(),'candidate':a.candidate.resolve()}; results={k:[] for k in bins}
with tempfile.TemporaryDirectory(prefix='sd-a-percentiles-') as temp:
 env=dict(os.environ,SD_DATA=str(a.data.resolve()),SD_OUT=temp,SD_THREADS=str(a.threads))
 for i in range(a.runs+1):
  order=list(bins); random.Random(597+i).shuffle(order)
  for name in order:
   start=time.perf_counter(); proc=subprocess.Popen([str(bins[name])],env=env); _,status,usage=os.wait4(proc.pid,0)
   elapsed=time.perf_counter()-start; proc.returncode=os.waitstatus_to_exitcode(status)
   if proc.returncode: raise RuntimeError((name,proc.returncode))
   digest=hashlib.sha256((pathlib.Path(temp)/'summary.txt').read_bytes()).hexdigest()
   if digest!=a.expected: raise RuntimeError((name,digest))
   if i: results[name].append({'wall_s':elapsed,'cpu_s':usage.ru_utime+usage.ru_stime,'ru_maxrss':usage.ru_maxrss,'sha256':digest})
report={'description':'Native measurements; ru_maxrss is bytes on macOS and KiB on Linux, not cgroup peak','threads':a.threads,'expected':a.expected,'results':results,'medians':{k:{m:statistics.median(row[m] for row in v) for m in ('wall_s','cpu_s','ru_maxrss')} for k,v in results.items()}}
a.report.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report['medians'],indent=2))

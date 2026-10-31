#!/usr/bin/env python3
"""Compare Rust A worker counts on an existing dataset; verify every output hash."""
import argparse, hashlib, json, os, pathlib, random, statistics, subprocess, tempfile, time
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary',required=True,type=pathlib.Path)
p.add_argument('--data',required=True,type=pathlib.Path)
p.add_argument('--expected',default='495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3')
p.add_argument('--runs',type=int,default=7)
p.add_argument('--report',required=True,type=pathlib.Path)
a=p.parse_args(); binary=a.binary.resolve(); data=a.data.resolve(); counts=[6,12]; results={str(n):[] for n in counts}
with tempfile.TemporaryDirectory(prefix='sd-a-workers-') as temp:
 out=pathlib.Path(temp)
 def run(n,save):
  env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_THREADS=str(n))
  start=time.perf_counter(); child=subprocess.Popen([str(binary)],env=env)
  _,status,usage=os.wait4(child.pid,0); elapsed=time.perf_counter()-start; child.returncode=os.waitstatus_to_exitcode(status)
  if child.returncode: raise RuntimeError((n,child.returncode))
  h=hashlib.sha256((out/'summary.txt').read_bytes()).hexdigest()
  if h!=a.expected: raise RuntimeError((n,h))
  if save: results[str(n)].append({'wall_s':elapsed,'cpu_s':usage.ru_utime+usage.ru_stime,'ru_maxrss':usage.ru_maxrss,'sha256':h})
 for n in counts: run(n,False)
 for i in range(a.runs):
  order=counts[:]; random.Random(20261031+i).shuffle(order)
  for n in order: run(n,True)
report={'description':'Native process timing; ru_maxrss is bytes on macOS, KiB on Linux, and is not cgroup peak','binary':str(binary),'data':str(data),'expected':a.expected,'results':results,'medians':{n:{m:statistics.median(row[m] for row in rows) for m in ('wall_s','cpu_s','ru_maxrss')} for n,rows in results.items()}}
a.report.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report['medians'],indent=2))

#!/usr/bin/env python3
"""Offline native comparison; output is not official cgroup scoring."""
import argparse,hashlib,json,os,pathlib,platform,random,statistics,subprocess,tempfile,time
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',required=True,type=pathlib.Path);p.add_argument('--report',required=True,type=pathlib.Path);p.add_argument('--runs',type=int,default=9);p.add_argument('--threads',type=int,default=12);p.add_argument('--generic',action='store_true');a=p.parse_args()
if a.runs<1 or a.threads<1:p.error('runs and threads must be positive')
root=pathlib.Path(__file__).resolve().parent; data=a.data.resolve();expected='495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3'
records={n:[] for n in ('baseline','candidate')};rng=random.Random(1071)
with tempfile.TemporaryDirectory(prefix='sd-a-dual-') as tmp:
 t=pathlib.Path(tmp);out=t/'out';out.mkdir()
 for n in records:
  flags=['rustc','--edition','2021','-O','-C','lto=fat','-C','codegen-units=1','-C','panic=abort']
  if not a.generic and platform.machine() in ('x86_64','amd64'):flags+=['-C','target-cpu=x86-64-v3']
  subprocess.run(flags+[str(root/(n+'.rs')),'-o',str(t/n)],check=True)
 for i in range(a.runs+1):
  order=list(records);rng.shuffle(order)
  for n in order:
   env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_THREADS=str(a.threads));start=time.perf_counter();q=subprocess.Popen([str(t/n)],env=env,stdout=subprocess.DEVNULL);_,status,u=os.wait4(q.pid,0);elapsed=time.perf_counter()-start
   if os.waitstatus_to_exitcode(status):raise SystemExit(f'{n}: nonzero exit')
   digest=hashlib.sha256((out/'summary.txt').read_bytes()).hexdigest()
   if digest!=expected:raise SystemExit(f'{n}: hash mismatch {digest}')
   if i:records[n].append({'wall_s':elapsed,'cpu_s':u.ru_utime+u.ru_stime,'ru_maxrss':u.ru_maxrss,'sha256':digest})
report={'note':'Native time includes startup; ru_maxrss is KiB on Linux, not warmed cgroup memory.','platform':platform.platform(),'rustc':subprocess.check_output(['rustc','--version'],text=True).strip(),'source_sha256':{n:hashlib.sha256((root/(n+'.rs')).read_bytes()).hexdigest() for n in records},'threads':a.threads,'runs':records,'medians':{n:{x:statistics.median(v[x] for v in rows) for x in ('wall_s','cpu_s','ru_maxrss')} for n,rows in records.items()}}
a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['medians'],indent=2))

#!/usr/bin/env python3
"""Offline, paired native benchmark; process RSS is not cgroup memory."""
import argparse, hashlib, json, os, platform, random, statistics, subprocess, tempfile, time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--data',type=Path,required=True); p.add_argument('--build-dir',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
p.add_argument('--seed',type=int,default=8681);p.add_argument('--runs',type=int,default=5);p.add_argument('--warmups',type=int,default=1);p.add_argument('--expected',default='a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e');p.add_argument('--generic',action='store_true',help='do not enable x86-64-v3')
a=p.parse_args()
if a.runs<1 or a.warmups<0 or not a.data.is_dir():p.error('invalid runs, warmups or data directory')
root=Path(__file__).resolve().parent; build=a.build_dir.resolve(); build.mkdir(parents=True,exist_ok=True); data=a.data.resolve(); bins={}
flags=['--edition=2021','-C','opt-level=3','-C','lto=fat','-C','codegen-units=1','-C','panic=abort']
if not a.generic and platform.machine().lower() in ('x86_64','amd64'): flags+=['-C','target-cpu=x86-64-v3']
for name in ('baseline','candidate'):
 bins[name]=build/name; subprocess.run(['rustc',*flags,str(root/(name+'.rs')),'-o',str(bins[name])],check=True)
rows=[]; rng=random.Random(a.seed)
with tempfile.TemporaryDirectory(prefix='d-meeting-bench-') as tmp:
 env=dict(os.environ,SD_DATA=str(data),SD_OUT=tmp); output=Path(tmp)/'distances.txt'
 for i in range(-a.warmups,a.runs):
  names=['baseline','candidate']; rng.shuffle(names)
  for name in names:
   output.unlink(missing_ok=True); start=time.monotonic(); proc=subprocess.Popen([str(bins[name])],env=env)
   _,status,ru=os.wait4(proc.pid,0); elapsed=time.monotonic()-start
   if os.waitstatus_to_exitcode(status)!=0: raise RuntimeError(f'{name} failed: {status}')
   digest=hashlib.sha256(output.read_bytes()).hexdigest()
   if digest!=a.expected: raise RuntimeError(f'{name} hash mismatch: {digest}')
   row=dict(iteration=i,name=name,wall_s=elapsed,cpu_s=ru.ru_utime+ru.ru_stime,maxrss_native=ru.ru_maxrss,sha256=digest);rows.append(row);print(json.dumps(row),flush=True)
summary={name:{'median_wall_s':statistics.median(r['wall_s'] for r in rows if r['name']==name and r['iteration']>=0),'median_cpu_s':statistics.median(r['cpu_s'] for r in rows if r['name']==name and r['iteration']>=0),'max_rss_native':max(r['maxrss_native'] for r in rows if r['name']==name and r['iteration']>=0)} for name in bins}
report=dict(platform=platform.platform(),rustc=subprocess.check_output(['rustc','--version'],text=True).strip(),flags=flags,source_sha256={n:hashlib.sha256((root/(n+'.rs')).read_bytes()).hexdigest() for n in bins},runs=rows,summary=summary,rss_note='Linux KiB, macOS bytes; process RSS is not cgroup memory')
a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary,indent=2))

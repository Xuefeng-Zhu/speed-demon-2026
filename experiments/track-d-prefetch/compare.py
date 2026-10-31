#!/usr/bin/env python3
"""Build and compare D prefetch variants; native timing is not cgroup scoring."""
import argparse,hashlib,json,os,platform,random,statistics,subprocess,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
NAMES=('baseline','prefetch1','prefetch2','prefetch4')
EXPECTED='a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--data',type=Path,required=True);p.add_argument('--runs',type=int,default=4);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();assert a.runs>0;data=a.data.resolve()
with tempfile.TemporaryDirectory(prefix='speed-d-order-') as td:
 root=Path(td); binaries={};samples={n:[] for n in NAMES}
 for n in NAMES:
  binary=root/n;subprocess.run(['rustc','--edition=2021','-C','opt-level=3','-C','lto=fat','-C','codegen-units=1','-C','panic=abort',*(['-C','target-cpu=x86-64-v3'] if platform.machine().lower() in ('x86_64','amd64') else []),str(HERE/f'{n}.rs'),'-o',str(binary)],check=True);binaries[n]=binary
 rng=random.Random(573)
 for iteration in range(a.runs+1):
  order=list(NAMES);rng.shuffle(order)
  for n in order:
   out=root/('out-'+n);out.mkdir(exist_ok=True);result=out/'distances.txt';result.unlink(missing_ok=True)
   start=time.perf_counter();proc=subprocess.Popen([str(binaries[n])],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),stdout=subprocess.DEVNULL)
   _,status,u=os.wait4(proc.pid,0);elapsed=time.perf_counter()-start
   if os.waitstatus_to_exitcode(status)!=0 or hashlib.sha256(result.read_bytes()).hexdigest()!=EXPECTED:raise SystemExit(f'{n}: exit or hash mismatch')
   if iteration:samples[n].append({'wall_s':elapsed,'cpu_s':u.ru_utime+u.ru_stime,'rss':u.ru_maxrss})
   print(iteration,n,round(elapsed,5),flush=True)
 report={'note':'one warmup then randomized rotations, full hash checked; process RSS is not cgroup memory','samples':samples,'medians':{n:{k:statistics.median(x[k] for x in v) for k in ('wall_s','cpu_s','rss')} for n,v in samples.items()}}
 a.report.write_text(json.dumps(report,indent=2)+'\n')

import argparse,hashlib,json,os,platform,random,statistics,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,required=True);p.add_argument('--build-dir',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--runs',type=int,default=7);p.add_argument('--seed',type=int,default=34192);p.add_argument('--shifts',nargs='+',type=int,default=[3,4,5,6,7,8,9,10]);a=p.parse_args()
root=Path(__file__).resolve().parent; a.build_dir.mkdir(parents=True,exist_ok=True);flags=['--edition=2021','-C','opt-level=3','-C','lto=fat','-C','codegen-units=1','-C','panic=abort'];bins={}
for shift in a.shifts:
 src=root/f'shift{shift}.rs';out=(a.build_dir/f'shift{shift}').resolve();subprocess.run(['rustc',*flags,str(src),'-o',str(out)],check=True);bins[shift]=out
rows=[];rng=random.Random(a.seed)
with tempfile.TemporaryDirectory(prefix='d-width25-') as tmp:
 env=dict(os.environ,SD_DATA=str(a.data.resolve()),SD_OUT=tmp);out=Path(tmp)/'distances.txt'
 for i in range(-1,a.runs):
  order=list(a.shifts);rng.shuffle(order)
  for shift in order:
   out.unlink(missing_ok=True);start=time.monotonic();pr=subprocess.Popen([str(bins[shift])],env=env);_,st,usage=os.wait4(pr.pid,0);wall=time.monotonic()-start
   digest=hashlib.sha256(out.read_bytes()).hexdigest() if os.waitstatus_to_exitcode(st)==0 else None
   assert digest=='a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e',(shift,st,digest)
   rows.append(dict(iteration=i,shift=shift,wall_s=wall,cpu_s=usage.ru_utime+usage.ru_stime,rss=usage.ru_maxrss,sha256=digest))
summary={str(n):dict(median_wall_s=statistics.median(r['wall_s'] for r in rows if r['shift']==n and r['iteration']>=0),median_cpu_s=statistics.median(r['cpu_s'] for r in rows if r['shift']==n and r['iteration']>=0),max_rss=max(r['rss'] for r in rows if r['shift']==n)) for n in a.shifts}
a.report.write_text(json.dumps(dict(platform=platform.platform(),flags=flags,source_hashes={str(n):hashlib.sha256((root/f'shift{n}.rs').read_bytes()).hexdigest() for n in a.shifts},runs=rows,summary=summary,rss_note='macOS bytes, native RSS, not cgroup'),indent=2)+'\n');print(json.dumps(summary,indent=2))

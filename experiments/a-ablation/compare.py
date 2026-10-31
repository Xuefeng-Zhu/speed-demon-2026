#!/usr/bin/env python3
"""Compare exact A ablations. Native RSS/faults are not official cgroup measurements."""
import argparse,ctypes,hashlib,json,mmap,os,pathlib,platform,random,statistics,subprocess,tempfile,time
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',required=True,type=pathlib.Path);p.add_argument('--report',required=True,type=pathlib.Path);p.add_argument('--runs',type=int,default=7);p.add_argument('--threads',type=int,default=12);p.add_argument('--sum-threads',type=int);p.add_argument('--generic',action='store_true');p.add_argument('--drop-cache',action='store_true',help='DONTNEED input file before each run; use only a disposable data copy');p.add_argument('--variants',nargs='+',choices=('baseline','reuse','cache','reserve','workers','no-madvise'),default=['baseline','reuse','cache','reserve','no-madvise']);a=p.parse_args()
if a.runs<1 or a.threads<1 or (a.sum_threads is not None and a.sum_threads<1):p.error('worker counts and runs must be positive')
if len(set(a.variants))!=len(a.variants):p.error('duplicate variants')
root=pathlib.Path(__file__).resolve().parent;data=a.data.resolve();log=data/'requests.log';expected='495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3';rng=random.Random(891);runs={n:[] for n in a.variants}
def residency(fd):
 size=os.fstat(fd).st_size; pages=(size+mmap.PAGESIZE-1)//mmap.PAGESIZE
 with mmap.mmap(fd,size,access=mmap.ACCESS_COPY) as m:
  address=ctypes.addressof(ctypes.c_char.from_buffer(m));vec=(ctypes.c_ubyte*pages)();libc=ctypes.CDLL(None,use_errno=True)
  if libc.mincore(ctypes.c_void_p(address),ctypes.c_size_t(size),vec):raise OSError(ctypes.get_errno(),'mincore failed')
  return {'resident_pages':sum(x&1 for x in vec),'total_pages':pages}
with tempfile.TemporaryDirectory(prefix='sd-a-ablation-') as tmp:
 t=pathlib.Path(tmp);out=t/'out';out.mkdir()
 for n in a.variants:
  flags=['rustc','--edition','2021','-O','-C','lto=fat','-C','codegen-units=1','-C','panic=abort']
  if not a.generic and platform.machine() in ('x86_64','amd64'):flags+=['-C','target-cpu=x86-64-v3']
  subprocess.run(flags+[str(root/(n+'-linux.rs')),'-o',str(t/n)],check=True)
 for i in range(a.runs+1):
  order=list(runs);rng.shuffle(order)
  for n in order:
   pre=None
   if a.drop_cache:
    with log.open('rb') as f:
     os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED);pre=residency(f.fileno())
   env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_THREADS=str(a.threads));
   if a.sum_threads is not None:env['SD_SUM_THREADS']=str(a.sum_threads)
   start=time.perf_counter();q=subprocess.Popen([str(t/n)],env=env,stdout=subprocess.DEVNULL);_,status,u=os.wait4(q.pid,0);elapsed=time.perf_counter()-start
   if os.waitstatus_to_exitcode(status):raise SystemExit(f'{n}: nonzero exit')
   digest=hashlib.sha256((out/'summary.txt').read_bytes()).hexdigest()
   if digest!=expected:raise SystemExit(f'{n}: hash mismatch {digest}')
   if i:runs[n].append({'wall_s':elapsed,'cpu_s':u.ru_utime+u.ru_stime,'ru_maxrss':u.ru_maxrss,'minor_faults':u.ru_minflt,'major_faults':u.ru_majflt,'cache_before':pre,'sha256':digest})
report={'note':'Native elapsed includes startup; Linux ru_maxrss is KiB, not cgroup memory; residency is a per-run snapshot, not guarantee of coldness.','platform':platform.platform(),'rustc':subprocess.check_output(['rustc','--version'],text=True).strip(),'source_sha256':{n:hashlib.sha256((root/(n+'-linux.rs')).read_bytes()).hexdigest() for n in runs},'threads':a.threads,'sum_threads':a.sum_threads,'drop_cache':a.drop_cache,'runs':runs,'medians':{n:{x:statistics.median(row[x] for row in rows) for x in ('wall_s','cpu_s','ru_maxrss','minor_faults','major_faults')} for n,rows in runs.items()}}
a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['medians'],indent=2))

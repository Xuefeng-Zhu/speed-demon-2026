#!/usr/bin/env python3
"""Offline interleaved comparison. RSS is per process, not cgroup memory."""
import argparse,hashlib,json,os,platform,random,statistics,subprocess,tempfile,time
from pathlib import Path
P=Path(__file__).resolve().parent

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--data',required=True,type=Path);ap.add_argument('--expected',default='f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927')
 ap.add_argument('--variants',nargs='+',default=['baseline','candidate'],choices=['baseline','candidate']);ap.add_argument('--runs',type=int,default=6);ap.add_argument('--warmups',type=int,default=1)
 ap.add_argument('--compiler',default='g++');ap.add_argument('--report',type=Path,default=Path('comparison.json'))
 a=ap.parse_args();assert a.runs>0 and a.warmups>=0 and len(set(a.variants))==len(a.variants)
 docs=a.data.resolve()/'docs.txt';queries=a.data.resolve()/'queries.txt';rng=random.Random(2147)
 report={'platform':platform.platform(),'compiler':subprocess.check_output([a.compiler,'--version'],text=True).splitlines()[0], 'flags':['-std=c++17','-O3','-DNDEBUG','-pthread'], 'source_sha256':{n:sha(P/(n+'.cpp')) for n in a.variants},'input_sha256':{'docs':sha(docs),'queries':sha(queries)},'expected_sha256':a.expected,'rss_note':'wait4 ru_maxrss: KiB on Linux, bytes on macOS; not cgroup memory','measurements':{n:[] for n in a.variants}}
 with tempfile.TemporaryDirectory(prefix='b-length-compare-') as td:
  tmp=Path(td)
  for name in a.variants:subprocess.run([a.compiler,*report['flags'],str(P/(name+'.cpp')),'-o',str(tmp/name)],check=True)
  for i in range(-a.warmups,a.runs):
   order=a.variants.copy();rng.shuffle(order)
   for name in order:
    with tempfile.TemporaryDirectory(dir=tmp,prefix=name+'-') as od:
     out=Path(od)/'results.txt';start=time.perf_counter();proc=subprocess.Popen([str(tmp/name),str(docs),str(queries),str(out)],stdout=subprocess.DEVNULL)
     _,status,usage=os.wait4(proc.pid,0);elapsed=time.perf_counter()-start;proc.returncode=os.waitstatus_to_exitcode(status)
     if proc.returncode:raise SystemExit(f'{name}: exit {proc.returncode}')
     digest=sha(out)
     if digest.lower()!=a.expected.lower():raise SystemExit(f'{name}: wrong output SHA-256 {digest}')
     row={'wall_s':elapsed,'user_s':usage.ru_utime,'system_s':usage.ru_stime,'max_rss_native_units':usage.ru_maxrss,'output_sha256':digest}
     print(('warmup' if i<0 else str(i+1)),name,row,flush=True)
     if i>=0:report['measurements'][name].append(row)
 for n in a.variants:
  report[n+'_median_wall_s']=statistics.median(x['wall_s'] for x in report['measurements'][n]);report[n+'_max_rss_native_units']=max(x['max_rss_native_units'] for x in report['measurements'][n])
 a.report.write_text(json.dumps(report,indent=2)+'\n');print('wrote',a.report,flush=True)
if __name__=='__main__':main()

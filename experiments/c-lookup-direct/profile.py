#!/usr/bin/env python3
"""Instrument lookup construction only; NOT a scoring benchmark."""
import argparse,json,os,random,statistics,subprocess,tempfile
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,required=True);args=parser.parse_args()
root=Path(__file__).parent
names=['baseline','country','presize','combined']; results={n:[] for n in names}; rng=random.Random(9281)
with tempfile.TemporaryDirectory(prefix='c-lookup-profile-') as t:
 t=Path(t);bins={}
 for name in names:
  s=(root/(name+'.rs')).read_text(); a='fn main() {\n'; b='    let words = (unmatched + 1).div_ceil(64);\n'; assert s.count(a)==s.count(b)==1
  s=s.replace(a,a+'    let profile_timer = std::time::Instant::now();\n').replace(b,b+'    if std::env::var_os("SD_PROFILE_LOOKUP").is_some() { eprintln!("{}", profile_timer.elapsed().as_nanos()); return; }\n')
  path=t/(name+'.rs'); exe=t/name;path.write_text(s)
  subprocess.run(['rustc','--edition=2021','-O','-C','lto=fat','-C','codegen-units=1','-C','panic=abort',str(path),'-o',str(exe)],check=True);bins[name]=exe
 for r in range(22):
  order=names.copy();rng.shuffle(order)
  for name in order:
   env=dict(os.environ,SD_DATA=str(args.data.resolve()),SD_PROFILE_LOOKUP='1')
   proc=subprocess.run([str(bins[name])],env=env,check=True,capture_output=True,text=True,timeout=20)
   ns=int(proc.stderr.strip())
   if r:results[name].append(ns/1e6)
for name in names:print(name,'median_ms',round(statistics.median(results[name]),4),'range',round(min(results[name]),4),round(max(results[name]),4))
(root/'profile-report.json').write_text(json.dumps(results,indent=2)+'\n')

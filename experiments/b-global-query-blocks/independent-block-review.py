#!/usr/bin/env python3
"""Check unique-output query order across atomic block boundaries and schedules."""
import os, subprocess, sys, tempfile
from pathlib import Path
repo=Path(__file__).resolve().parents[2];s=(repo/'experiments/b-global-query-blocks/candidate.rs').read_text();ref=repo/'official/reference/b_index.py'
needle='let nthreads = thread::available_parallelism().map_or(4, |n| n.get());';assert s.count(needle)==1
push='owned.push((lo, answer_range(parts, plan, lo, hi, freqs, cache)));';assert s.count(push)==1
sort='    answers.sort_unstable_by_key(|(lo, _)| *lo);';assert s.count(sort)==1
with tempfile.TemporaryDirectory(prefix='b-block-independent-') as tmp:
 root=Path(tmp);data=root/'data';expected=root/'expected';actual=root/'actual'
 for p in (data,expected,actual):p.mkdir()
 docs=[f'{i}\tu{i} anchor marker\n' for i in range(1025)]
 (data/'docs.txt').write_text(''.join(docs))
 allq=[]
 for i in range(1025):
  token=f'u{i}'
  q=[f'BOOL {token}',f'BOOL {token} OR never',f'PHRASE "{token} anchor"',f'BOOL never OR {token} AND marker'][i%4]
  allq.append(q)
 bins=[]
 for workers in (1,2,7,32,64):
  text=s.replace(needle,f'let nthreads = {workers};');src=root/f's{workers}.rs';exe=root/f'e{workers}';src.write_text(text)
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True,stderr=subprocess.DEVNULL);bins.append(exe)
 delayed=s.replace(needle,'let nthreads = 7;').replace(push,'if lo == 0 { std::thread::sleep(std::time::Duration::from_millis(100)); } '+push)
 delay_src=root/'delayed.rs';delay_src.write_text(delayed);delay_exe=root/'delayed'
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(delay_src),'-o',str(delay_exe)],check=True,stderr=subprocess.DEVNULL)
 shuffled=delayed.replace(sort,'    answers.sort_unstable_by_key(|(lo, _)| std::cmp::Reverse(*lo));\n'+sort)
 shuffle_src=root/'shuffled.rs';shuffle_src.write_text(shuffled);shuffle_exe=root/'shuffled'
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(shuffle_src),'-o',str(shuffle_exe)],check=True,stderr=subprocess.DEVNULL)
 broken_src=root/'broken.rs';broken_src.write_text(shuffled.replace(sort,''));broken_exe=root/'broken'
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(broken_src),'-o',str(broken_exe)],check=True,stderr=subprocess.DEVNULL)
 for n in (0,1,2,255,256,257,511,512,513,767,768,769,1023,1024,1025):
  (data/'queries.txt').write_text(''.join(q+'\n' for q in allq[:n]));subprocess.run([sys.executable,str(ref),'--data',str(data),'--out',str(expected)],check=True,stdout=subprocess.DEVNULL)
  want=(expected/'results.txt').read_bytes();
  if n: assert want==''.join(f'1 {i} {i}\n' for i in range(n)).encode(),n
  env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(actual)}
  for workers,exe in zip((1,2,7,32,64),bins):
   subprocess.run([str(exe)],env=env,check=True,stdout=subprocess.DEVNULL);assert (actual/'results.txt').read_bytes()==want,(n,workers)
  if n==513:
   subprocess.run([str(delay_exe)],env=env,check=True);assert (actual/'results.txt').read_bytes()==want,'delayed valid ordering'
   subprocess.run([str(shuffle_exe)],env=env,check=True);assert (actual/'results.txt').read_bytes()==want,'descending block order is restored'
   subprocess.run([str(broken_exe)],env=env,check=True);assert (actual/'results.txt').read_bytes()!=want,'fixture failed to detect broken unsorted ordering'
   print('PASS delayed completion and forced reverse order; removing sort is detected',flush=True)
  print('PASS unique-signature queries',n,'workers 1/2/7/32/64',flush=True)

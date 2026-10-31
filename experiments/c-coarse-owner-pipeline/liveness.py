#!/usr/bin/env python3
"""Exact-source pipeline teardown and rendezvous stress; isolated temp files only."""
from pathlib import Path
import os, subprocess, sys, tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=(HERE/'candidate.rs').read_text()
def replace_once(s,old,new):
 assert s.count(old)==1,(old,s.count(old))
 return s.replace(old,new)
def variant(mode):
 s=BASE
 s=replace_once(s,'let n = thread::available_parallelism().map_or(1, |n| n.get()).min(12);','let n = 8usize;')
 s=replace_once(s,'const PIPE_BATCH: usize = 4096;','const PIPE_BATCH: usize = 4;')
 s=replace_once(s,'std::sync::mpsc::sync_channel::<Vec<Event>>(2)','std::sync::mpsc::sync_channel::<Vec<Event>>(0)')
 s=replace_once(s,'let (name, name_len, h) = field_name_hash(recs, &mut p);','let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;')
 if mode in ('owner_spawn','parser_spawn'):
  s=replace_once(s,'use std::collections::HashMap;','use std::collections::HashMap;\nstatic STARTED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);')
 if mode=='owner_spawn':
  s=replace_once(s,'for _ in 0..parts {\n                let (tx, rx)', 'for owner_index in 0..parts {\n                if owner_index == 1 { while !STARTED.load(std::sync::atomic::Ordering::Acquire) { thread::yield_now(); } panic!("INJECTED_OWNER_SPAWN"); }\n                let (tx, rx)')
  s=replace_once(s,'owners.push(sc.spawn(move || {','owners.push(sc.spawn(move || {\n                    STARTED.store(true, std::sync::atomic::Ordering::Release);')
 if mode=='parser_spawn':
  s=replace_once(s,'for _ in 0..n {\n                let senders = senders.clone();', 'for parser_index in 0..n {\n                if parser_index == 1 { while !STARTED.load(std::sync::atomic::Ordering::Acquire) { thread::yield_now(); } panic!("INJECTED_PARSER_SPAWN"); }\n                let senders = senders.clone();')
  s=replace_once(s,'parsers.push(sc.spawn(move || {','parsers.push(sc.spawn(move || {\n                    STARTED.store(true, std::sync::atomic::Ordering::Release);')
 if mode=='owner_panic':
  s=replace_once(s,'while let Ok(events) = rx.recv() {','while let Ok(events) = rx.recv() {\n                        if !events.is_empty() { panic!("INJECTED_OWNER"); }')
 if mode=='parser_panic':
  old='let id = positive_fast(recs, &mut p);'; assert s.count(old)==2
  s=s.replace(old,old+' if id == 500 { panic!("INJECTED_PARSER"); }',1)
 return s
with tempfile.TemporaryDirectory(prefix='c-coarse-live-') as tmp:
 root=Path(tmp);data=root/'data';ref=root/'ref';data.mkdir();ref.mkdir()
 (data/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n2,BBB\n')
 body=b''.join(f'{i},"n{i%41}","x",{1+i%2},{i%8}.00\r\n'.encode() for i in range(1,2001))
 (data/'records.csv').write_bytes(b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'+body)
 subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,timeout=30)
 expected=(ref/'aggregates.txt').read_bytes()
 for mode in ('normal','owner_spawn','parser_spawn','owner_panic','parser_panic'):
  source=root/f'{mode}.rs';exe=root/mode;out=root/f'{mode}-out';out.mkdir();source.write_text(variant(mode))
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(source),'-o',str(exe)],check=True,timeout=40)
  r=subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),capture_output=True,timeout=30)
  if mode=='normal':
   assert r.returncode==0,(mode,r.stderr.decode()[-2000:]); assert (out/'aggregates.txt').read_bytes()==expected
  else:
   assert r.returncode!=0,(mode,r.returncode);assert b'INJECTED_' in r.stderr,(mode,r.stderr.decode()[-2000:]);assert not (out/'aggregates.txt').exists(),mode
  print('PASS',mode,'rendezvous channel, no deadlock')

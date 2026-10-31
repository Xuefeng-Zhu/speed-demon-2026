#!/usr/bin/env python3
"""Run phase-instrumented binary, verify the public seed-1 output, save raw observations."""
import argparse, hashlib, json, os, pathlib, statistics, subprocess, tempfile, time
p=argparse.ArgumentParser(); p.add_argument('--binary',required=True); p.add_argument('--data',required=True); p.add_argument('--runs',type=int,default=5); p.add_argument('--report',required=True); a=p.parse_args()
expected='f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
rows=[]
with tempfile.TemporaryDirectory(prefix='sd-b-phase-') as out:
 for run in range(-1,a.runs):
  start=time.monotonic(); r=subprocess.run([a.binary],env={**os.environ,'SD_DATA':a.data,'SD_OUT':out},capture_output=True,text=True,check=True); wall=time.monotonic()-start
  h=hashlib.sha256((pathlib.Path(out)/'results.txt').read_bytes()).hexdigest(); assert h==expected,(run,h)
  phases={}; blocks=[]; indexes=[]; calls=[]
  for line in r.stderr.splitlines():
   x=line.split()
   if len(x)==3 and x[0]=='PHASE': phases[x[1]]=int(x[2])/1e9
   elif len(x)==5 and x[0]=='IDX': indexes.append({'lo':int(x[1]),'ndocs':int(x[2]),'scan_s':int(x[3])/1e9,'total_s':int(x[4])/1e9})
   elif len(x)==5 and x[0]=='BLOCK': blocks.append({'lo':int(x[1]),'hi':int(x[2]),'bool_queries':int(x[3]),'seconds':int(x[4])/1e9})
   elif len(x)==6 and x[0]=='CALL': calls.append({'lo':int(x[1]),'hi':int(x[2]),'docs':int(x[3]),'callback_s':int(x[4])/1e9,'total_s':int(x[5])/1e9})
   else: raise ValueError(line)
  assert len(phases)==10 and blocks and indexes,(phases,len(blocks),len(indexes))
  rows.append({'run':run,'warmup':run<0,'wall_s':wall,'sha256':h,'phases':phases,'indexes':indexes,'blocks':blocks,'calls':calls})
measured=[x for x in rows if not x['warmup']]
phase_names=measured[0]['phases']
summary={'median_wall_s':statistics.median(x['wall_s'] for x in measured),'median_phase_s':{k:statistics.median(x['phases'][k] for x in measured) for k in phase_names},'median_index_worker_max_s':statistics.median(max(z['total_s'] for z in x['indexes']) for x in measured),'median_index_scan_worker_sum_s':statistics.median(sum(z['scan_s'] for z in x['indexes']) for x in measured),'median_index_csr_worker_sum_s':statistics.median(sum(z['total_s']-z['scan_s'] for z in x['indexes']) for x in measured),'median_answer_block_elapsed_sum_s':statistics.median(sum(z['seconds'] for z in x['blocks']) for x in measured),'median_answer_block_max_s':statistics.median(max(z['seconds'] for z in x['blocks']) for x in measured)}
pathlib.Path(a.report).write_text(json.dumps({'summary':summary,'runs':rows},indent=2)+'\n');print(json.dumps(summary,indent=2))

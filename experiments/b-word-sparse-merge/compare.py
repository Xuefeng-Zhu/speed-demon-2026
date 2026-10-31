#!/usr/bin/env python3
"""Randomized paired native measurements with a supplied reference hash."""
import argparse
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--data',type=Path,required=True)
p.add_argument('--expected',required=True)
p.add_argument('--runs',type=int,default=15)
p.add_argument('--seed',type=int,default=7861)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args()
if a.runs<1: p.error('--runs must be positive')
bins={name:str(getattr(a,name).resolve(strict=True)) for name in ('baseline','candidate')}
results={name:[] for name in bins}
with tempfile.TemporaryDirectory(prefix='sd-b-word-timing-') as tmp:
    tmp=Path(tmp)
    for run in range(a.runs+1):
        order=list(bins); random.Random(a.seed+run).shuffle(order)
        for name in order:
            out=tmp/f'{run}-{name}';out.mkdir()
            env={**os.environ,'SD_DATA':str(a.data.resolve()),'SD_OUT':str(out)}
            start=time.perf_counter()
            proc=subprocess.Popen([bins[name]],env=env,stdout=subprocess.DEVNULL)
            _,status,usage=os.wait4(proc.pid,0)
            wall=time.perf_counter()-start
            if os.waitstatus_to_exitcode(status): raise RuntimeError(f'{name} failed {status}')
            got=hashlib.sha256((out/'results.txt').read_bytes()).hexdigest()
            if got!=a.expected: raise RuntimeError(f'{name} output {got} != {a.expected}')
            results[name].append({'wall_s':wall,'cpu_s':usage.ru_utime+usage.ru_stime,'rss_native':usage.ru_maxrss,'warmup':run==0})
summary={}
for name,rows in results.items():
    summary[name]={k:statistics.median(row[k] for row in rows[1:]) for k in ('wall_s','cpu_s','rss_native')}
    print(name,summary[name],flush=True)
a.report.write_text(json.dumps({'platform':platform.platform(),'expected':a.expected,'dataset':str(a.data),'runs':results,'summary':summary,'rss_note':'macOS bytes; Linux KiB; process RSS is not parent-cgroup peak'},indent=2)+'\n')

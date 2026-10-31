#!/usr/bin/env python3
"""Run instrumented C and count owner cache behavior; not a timing benchmark."""
import argparse, hashlib, json, os, pathlib, re, subprocess, tempfile

EXPECTED='d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536'
LINE=re.compile(r'^C_OWNER_DIAG hits=(\d+) misses=(\d+) unique_rows=(\d+) promoted_hashes=(\d+)$')
p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('data');p.add_argument('--runs',type=int,default=3);args=p.parse_args()
if args.runs < 1: p.error('--runs must be positive')
result=[]
for _ in range(args.runs):
    with tempfile.TemporaryDirectory(prefix='c-owner-diag-') as out:
        env=dict(os.environ, SD_DATA=str(pathlib.Path(args.data).resolve()), SD_OUT=out)
        proc=subprocess.run([str(pathlib.Path(args.binary).resolve())],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,text=True)
        raw=pathlib.Path(out,'aggregates.txt').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=EXPECTED: raise RuntimeError('unexpected public full-seed output hash')
        rows=[tuple(map(int,m.groups())) for line in proc.stderr.splitlines() if (m:=LINE.fullmatch(line))]
        if not rows: raise RuntimeError('no compact-owner diagnostics; fallback mode is not profiled')
        h,m,u,prom=(sum(v) for v in zip(*rows));distinct=sum(int(line.split()[6]) for line in raw.splitlines())
        result.append(dict(workers=len(rows),hits=h,misses=m,events=h+m,unique_rows=u,promoted_hashes=prom,distinct_pairs=distinct))
print(json.dumps({'dataset':'full public seed 1','note':'instrumented counts; not target timing or hidden-data evidence','runs':result},indent=2))

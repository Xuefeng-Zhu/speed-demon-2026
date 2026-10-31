#!/usr/bin/env python3
"""Require a non-full final outbound batch to be sent and accounted for."""
from pathlib import Path
import os, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
s=(Path(__file__).parent/'candidate.rs').read_text()
replacements={
'let n = thread::available_parallelism().map_or(1, |n| n.get());':'let n = 2usize;',
'const PIPE_BATCH: usize = 256;':'const PIPE_BATCH: usize = 257;',
'let (name, name_len, h) = field_name_hash(recs, &mut p);':'let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;',
'''                        if !bin.is_empty() {
                            flush_batch''':'''                        if !bin.is_empty() {
                            assert!(bin.len() < PIPE_BATCH); eprintln!("PARTIAL_FINAL_FLUSH");
                            flush_batch'''
}
for a,b in replacements.items(): assert s.count(a)==1,a;s=s.replace(a,b)
with tempfile.TemporaryDirectory(prefix='pipeline-partial-') as td:
 root=Path(td);data=root/'data';ref=root/'ref';out=root/'out'
 for p in (data,ref,out):p.mkdir()
 (data/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n')
 (data/'records.csv').write_bytes(b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'+b''.join(f'{i},"name{i%500}","x",1,1.00\r\n'.encode() for i in range(1,1001)))
 subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,timeout=20)
 src=root/'test.rs';exe=root/'test';src.write_text(s)
 subprocess.run(['rustc','--edition=2021','-O',str(src),'-o',str(exe)],check=True,timeout=40)
 run=subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),capture_output=True,check=True,timeout=30)
 assert b'PARTIAL_FINAL_FLUSH' in run.stderr
 assert (out/'aggregates.txt').read_bytes()==(ref/'aggregates.txt').read_bytes()
 print('PASS observed non-full final batch routed and reference matched')

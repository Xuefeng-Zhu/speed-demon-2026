#!/usr/bin/env python3
"""Simulate parent unwind after one scoped worker has started."""
from pathlib import Path
import os,subprocess,tempfile
s=(Path(__file__).parent/'candidate.rs').read_text()
s=s.replace('//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.','')
s='static STARTED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);\n'+s
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
assert s.count(needle)==1;s=s.replace(needle,'let n = 8usize;')
needle='''                handles.push(scope.spawn(move || {
                    let mut guard = AbortGuard { abort, done: false };'''
assert s.count(needle)==1
s=s.replace(needle,'''                if t == 1 { while !STARTED.load(Ordering::Acquire) { thread::yield_now(); } panic!("INJECTED_PARENT_SPAWN_FAILURE"); }
                handles.push(scope.spawn(move || {
                    let mut guard = AbortGuard { abort, done: false };
                    STARTED.store(true, Ordering::Release);''')
with tempfile.TemporaryDirectory(prefix='pipeline-partial-spawn-') as tmp:
 root=Path(tmp);data=root/'data';out=root/'out';data.mkdir();out.mkdir()
 (data/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n')
 (data/'records.csv').write_bytes(b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'+b''.join(f'{i},"name{i}","x",1,1.00\r\n'.encode() for i in range(1,10001)))
 src=root/'test.rs';exe=root/'test';src.write_text(s)
 subprocess.run(['rustc','--edition=2021','-O',str(src),'-o',str(exe)],check=True,timeout=40)
 p=subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),capture_output=True,timeout=30)
 assert p.returncode != 0 and b'INJECTED_PARENT_SPAWN_FAILURE' in p.stderr
 assert not (out/'aggregates.txt').exists()
 print('PASS forced parent panic after an active worker, no hang or output')

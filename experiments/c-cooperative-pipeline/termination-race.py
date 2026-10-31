#!/usr/bin/env python3
"""Schedule the final send strictly between the receiver's first empty and zero check."""
from pathlib import Path
import os, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
s=(Path(__file__).parent/'candidate.rs').read_text()
s='static RACE_STATE: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);\n'+s.replace('//! Speed Demon 2026, Track C (Join): std-only Rust. README.md explains the design.','')
def replace_once(a,b):
 global s
 assert s.count(a)==1,a
 s=s.replace(a,b)
replace_once('let n = thread::available_parallelism().map_or(1, |n| n.get());','let n = 2usize;')
replace_once('const PIPE_BATCH: usize = 256;','const PIPE_BATCH: usize = 100000;')
replace_once('let (name, name_len, h) = field_name_hash(recs, &mut p);','let (name, name_len, _h) = field_name_hash(recs, &mut p); let h = 0u64;')
replace_once('''                    for (bucket, bin) in bins.iter_mut().enumerate() {''','''                    if t == 1 { while RACE_STATE.load(Ordering::Acquire) != 1 { thread::yield_now(); } }
                    for (bucket, bin) in bins.iter_mut().enumerate() {''')
replace_once('''                    remaining.fetch_sub(1, Ordering::AcqRel);''','''                    remaining.fetch_sub(1, Ordering::AcqRel);
                    if t == 1 { RACE_STATE.store(2, Ordering::Release); }''')
replace_once('''                            Err(mpsc::TryRecvError::Empty) => {
                                if remaining.load(Ordering::Acquire) == 0 {''','''                            Err(mpsc::TryRecvError::Empty) => {
                                if t == 0 && RACE_STATE.compare_exchange(0, 1, Ordering::AcqRel, Ordering::Acquire).is_ok() {
                                    while RACE_STATE.load(Ordering::Acquire) != 2 { thread::yield_now(); }
                                }
                                if remaining.load(Ordering::Acquire) == 0 {''')
new='''                                    // A producer can send between the first empty read and zero.
                                    match rx.try_recv() {
                                        Ok(batch) => reduce_batch(batch, recs, &mut dict, &mut counts, words),
                                        Err(mpsc::TryRecvError::Empty) => break,
                                        Err(mpsc::TryRecvError::Disconnected) => panic!("pipeline inbox disconnected"),
                                    }'''
assert s.count(new)==1
with tempfile.TemporaryDirectory(prefix='pipeline-race-') as tmp:
 root=Path(tmp);data=root/'data';ref=root/'ref';data.mkdir();ref.mkdir()
 (data/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n')
 (data/'records.csv').write_bytes(b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'+b''.join(f'{i},"name{i}","x",1,1.00\r\n'.encode() for i in range(1,501)))
 subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,timeout=20)
 expected=(ref/'aggregates.txt').read_bytes()
 for label,body in [('fixed',s),('old_bug',s.replace(new,'break;'))]:
  src=root/(label+'.rs');exe=root/label;src.write_text(body)
  subprocess.run(['rustc','--edition=2021','-O',str(src),'-o',str(exe)],check=True,timeout=30)
  out=root/label;out=Path(str(out)+'-out');out.mkdir()
  subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True,timeout=30)
  got=(out/'aggregates.txt').read_bytes()
  assert (got==expected)==(label=='fixed'),(label,got,expected)
  print('PASS',label,'recheck prevents lost final batch' if label=='fixed' else 'old race reproduced')

#!/usr/bin/env python3
"""Force full queues, oversubscription and worker failures; requires only standard tools."""
from pathlib import Path
import os, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(__file__).parent/'candidate.rs').read_text()
source=source.replace('const PIPE_BATCH: usize = 256;', 'const PIPE_BATCH: usize = 1;').replace('const PIPE_INBOX: usize = 2;', 'const PIPE_INBOX: usize = 1;')
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
assert source.count(needle)==1
source=source.replace(needle, 'let n = std::env::var("SD_TEST_WORKERS").unwrap().parse::<usize>().unwrap();')
full='''Err(TrySendError::Full(b)) => {
                batch = b;'''
assert source.count(full)==1
fulltrace='''Err(TrySendError::Full(b)) => {
                static SEEN: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
                if !SEEN.swap(true, Ordering::Relaxed) { eprintln!("FULL_QUEUE_EXERCISED"); }
                batch = b;'''
normal=source.replace(full,fulltrace)
parse_line='''                    while p < end {
                        assert!(!abort.load(Ordering::Acquire), "pipeline worker aborted");'''
assert normal.count(parse_line)==1
panicparse=normal.replace(parse_line,parse_line+'''
                        if t == 0 && parsed == 20 { panic!("INJECTED_PARSE_PANIC"); }''')
panicfull=normal.replace(fulltrace,fulltrace.replace('                batch = b;', '                panic!("INJECTED_FULL_PANIC");'))
with tempfile.TemporaryDirectory(prefix='pipeline-stress-') as td:
 root=Path(td);data=root/'data';data.mkdir();ref=root/'ref';ref.mkdir()
 (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},AA{chr(65+i)}\n' for i in range(8)))
 rows=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
 for i in range(1,16001):
  name=f'Name {i%997:04d}' + (' ' if i%19==0 else '')
  rows.append(f'{i},"{name}","ab\ncd",{1+i%8},-1.25\r\n'.encode())
 (data/'records.csv').write_bytes(b''.join(rows))
 subprocess.run([sys.executable,str(ROOT/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL,timeout=60)
 expected=(ref/'aggregates.txt').read_bytes()
 for label,body in [('normal',normal),('panic_parse',panicparse),('panic_full',panicfull)]:
  src=root/(label+'.rs'); exe=root/label; src.write_text(body)
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True,timeout=90,stderr=subprocess.DEVNULL if label=='panic_full' else None)
  for n in ([1,2,7,32,64] if label=='normal' else [7,32]):
   out=root/f'{label}-{n}';out.mkdir()
   run=subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_TEST_WORKERS=str(n)),capture_output=True,timeout=60)
   if label=='normal':
    assert run.returncode==0,run.stderr.decode()
    assert (out/'aggregates.txt').read_bytes()==expected,(label,n)
    if n>=2: assert b'FULL_QUEUE_EXERCISED' in run.stderr,(label,n)
   else:
    assert run.returncode != 0,(label,n)
    assert (b'INJECTED_PARSE_PANIC' if label=='panic_parse' else b'INJECTED_FULL_PANIC') in run.stderr,(label,n,run.stderr)
    assert not (out/'aggregates.txt').exists(),(label,n)
   print('PASS',label,'workers',n,flush=True)

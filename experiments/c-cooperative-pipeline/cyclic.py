#!/usr/bin/env python3
"""All inboxes full, all senders simultaneously stalled before any drain."""
from pathlib import Path
import subprocess, tempfile
s=(Path(__file__).parent/'candidate.rs').read_text()
needle='''    use std::sync::{atomic::Ordering, mpsc::TrySendError};
    loop {'''
assert s.count(needle)==1
s=s.replace(needle,'''    use std::sync::{atomic::Ordering, mpsc::TrySendError};
    let mut first_full = true;
    loop {''')
needle='''            Err(TrySendError::Full(b)) => {
                batch = b;'''
assert s.count(needle)==1
s=s.replace(needle,'''            Err(TrySendError::Full(b)) => {
                if first_full {
                    first_full = false;
                    CYCLIC_READY.fetch_add(1, Ordering::AcqRel);
                    while CYCLIC_READY.load(Ordering::Acquire) != CYCLIC_N.load(Ordering::Acquire) { thread::yield_now(); }
                }
                batch = b;''')
tail=r'''
static CYCLIC_N: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
static CYCLIC_READY: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
#[test]
fn saturated_cycle_progress() {
 use std::sync::{atomic::{AtomicBool, Ordering}, mpsc, Barrier};
 for n in [2usize,7,32,64] {
  CYCLIC_N.store(n, Ordering::Release); CYCLIC_READY.store(0, Ordering::Release);
  let abort=AtomicBool::new(false); let barrier=Barrier::new(n);
  let (senders, receivers): (Vec<_>,Vec<_>)=(0..n).map(|_|mpsc::sync_channel::<Vec<Event>>(1)).unzip();
  let base=Event{offset:0,len:1,group:0,hash:1};
  let sent=Event{offset:0,len:1,group:1,hash:1};
  for tx in &senders { tx.try_send(vec![base]).unwrap(); }
  thread::scope(|sc| {
   let mut threads=Vec::new();
   let (senders,abort,barrier)=(&senders,&abort,&barrier);
   for (i,rx) in receivers.into_iter().enumerate() {
    threads.push(sc.spawn(move || {
     let mut dict=OwnerDict::default(); let mut counts=[0i64;2]; let recs:&'static[u8]=b"x";
     flush_batch(vec![sent],&senders[(i+1)%n],&rx,recs,&mut dict,&mut counts,1,abort);
     barrier.wait();
     while let Ok(msg)=rx.try_recv(){reduce_batch(msg,recs,&mut dict,&mut counts,1);}
     assert_eq!(counts,[1,1]);
    }));
   }
   for t in threads { t.join().unwrap(); }
  });
  assert_eq!(CYCLIC_READY.load(Ordering::Acquire),n);
  eprintln!("PASS forced simultaneous full cycle workers={n}");
 }
}
'''
with tempfile.TemporaryDirectory(prefix='pipeline-cycle-') as td:
 src=Path(td)/'test.rs';exe=Path(td)/'test';src.write_text(s+'\n'+tail)
 subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True,timeout=60)
 subprocess.run([str(exe),'saturated_cycle_progress','--nocapture'],check=True,timeout=60)

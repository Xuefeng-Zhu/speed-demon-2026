#!/usr/bin/env python3
"""Instrument a temporary exact-source copy; never edit the candidate."""
import hashlib, pathlib, subprocess, tempfile

here = pathlib.Path(__file__).resolve().parent
src = here / 'candidate.rs'
s = src.read_text()
assert hashlib.sha256(s.encode()).hexdigest() == 'c33d3984871fb22ed7c2d678b3a3562ac82d46cb952a8a0461980301c5a553ef'
decl = '''
#[cfg(test)] static P_PRUNE: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_KNOWN_LT: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_KNOWN_GE: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_UNSEEN: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_ZERO_B: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_IMPROVE: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_FEMPTY: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_REMPTY: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_CUTOFF: AtomicU64=AtomicU64::new(0);
#[cfg(test)] static P_EXHAUST: AtomicU64=AtomicU64::new(0);
'''
marker = 'const POOL_CAP: usize = 65_536;'
assert s.count(marker)==1
s=s.replace(marker,decl+marker)
start="""        let mut best=NONE;let mut dropped=false;let mut exhausted=false;
        'search: while let (Some(a),Some(b))=(self.heaps[0].top(),self.heaps[1].top()) {"""
replacement="""        let mut best=NONE;let mut dropped=false;let mut exhausted=false;
        let mut test_pruned=false;
        'search: loop {
            let (oa,ob)=(self.heaps[0].top(),self.heaps[1].top());
            let (Some(a),Some(b))=(oa,ob) else {
                if test_pruned { if oa.is_none() { P_FEMPTY.fetch_add(1, Relaxed); } if ob.is_none() { P_REMPTY.fetch_add(1, Relaxed); } }
                break;
            };"""
assert s.count(start)==1
s=s.replace(start,replacement)
needle='''                    if nd>=u32::MAX as u64 {dropped=true;continue;}
                    // Backward search is unpruned.'''
assert s.count(needle)==1
s=s.replace(needle,'''                    if nd>=u32::MAX as u64 {P_CUTOFF.fetch_add(1, Relaxed);dropped=true;continue;}
                    // Backward search is unpruned.''')
branch='''                        let other = self.dist[v as usize][1];
                        if other != 0 { best = best.min(nd + (!other) as u64); }
                        continue;'''
inst='''                    test_pruned=true; P_PRUNE.fetch_add(1, Relaxed);
                    if b==0 { P_ZERO_B.fetch_add(1, Relaxed); }
                    let other = self.dist[v as usize][1];
                    if other == 0 { P_UNSEEN.fetch_add(1, Relaxed); }
                    else {
                        if ((!other) as u64) < b { P_KNOWN_LT.fetch_add(1, Relaxed); }
                        else { P_KNOWN_GE.fetch_add(1, Relaxed); }
                        if nd + ((!other) as u64) < best { P_IMPROVE.fetch_add(1, Relaxed); }
                        best = best.min(nd + (!other) as u64);
                    }
                    continue;'''
assert s.count(branch)==1
s=s.replace(branch,inst)
exhaust='''                        Err(())=>{exhausted=true;break 'search;},'''
assert s.count(exhaust)==1
s=s.replace(exhaust,'''                        Err(())=>{P_EXHAUST.fetch_add(1, Relaxed);exhausted=true;break 'search;},''')
tail=(here/'independent-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='d-forward-independent-') as temp:
    root=pathlib.Path(temp)
    for cap in (0,1,2,65536):
        test_src=root/f'cap{cap}.rs'; binary=root/f'cap{cap}'
        test_src.write_text(s.replace(marker,f'const POOL_CAP: usize = {cap};')+'\n'+tail)
        subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(test_src),'-o',str(binary)],check=True)
        subprocess.run([str(binary),'--nocapture','--test-threads=1'],check=True)

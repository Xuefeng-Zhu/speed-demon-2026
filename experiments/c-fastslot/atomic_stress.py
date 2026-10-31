from pathlib import Path
import subprocess, tempfile
s=Path('experiments/c-fastslot/candidate.rs').read_text()
s='\n'.join(('//' + line[3:] if line.startswith('//!') else line) for line in s.split('\n'))
s+='''
#[cfg(test)]
mod review {
    use super::*;
    use std::sync::Barrier;
    #[test]
    fn racing_collisions_are_exact() {
        for workers in [2usize, 8, 32] {
            for _ in 0..4 {
                let mut values: Vec<Vec<u8>> = (0..64).map(|i| format!("Name {i} ").into_bytes()).collect();
                values.extend([b"".to_vec(), b"Ann \\\"\\\"Annie\\\"\\\" Lee".to_vec(), b"Betts".to_vec(), b"Betts ".to_vec()]);
                let names1: Vec<&'static [u8]> = values.iter().map(|n| &*Box::leak(n.clone().into_boxed_slice())).collect();
                let names2: Vec<&'static [u8]> = values.iter().map(|n| &*Box::leak(n.clone().into_boxed_slice())).collect();
                let groups = [0usize,1,63,64,65,127,128,191,192,239,240,255,256,309];
                let shards: Vec<Shard> = (0..1024).map(|_| Shard::default()).collect();
                let slots: Vec<AtomicPtr<FastName>> = vec![AtomicPtr::new(std::ptr::null_mut())];
                let b = Barrier::new(workers);
                let total: i64 = thread::scope(|sc| {
                    let mut handles=Vec::new();
                    for tid in 0..workers {
                        let (names1,names2,slots,shards,b,groups)=(&names1,&names2,&slots,&shards,&b,&groups);
                        handles.push(sc.spawn(move || {
                            b.wait();
                            let mut count=0;
                            for j in 0..names1.len() {
                                let i = (j+tid) % names1.len();
                                for &g in groups {
                                    let name=if tid&1==0 {names1[i]} else {names2[i]};
                                    count += fast_see(slots,name,g,5,0,shards);
                                }
                            }
                            count
                        }));
                    }
                    handles.into_iter().map(|h|h.join().unwrap()).sum()
                });
                assert_eq!(total, (values.len()*groups.len()) as i64);
            }
        }
    }
}
'''
with tempfile.TemporaryDirectory(prefix='c-fastslot-atomic-') as tmp:
    p=Path(tmp)/'review.rs'; p.write_text(s)
    exe=Path(tmp)/'review'
    subprocess.run(['rustc','--edition=2021','--test','-C','opt-level=2','-C','overflow-checks=yes',str(p),'-o',str(exe)],check=True)
    subprocess.run([str(exe),'--nocapture'],check=True)

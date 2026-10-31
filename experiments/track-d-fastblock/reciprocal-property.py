from pathlib import Path
import re, subprocess, tempfile
source=Path('experiments/track-d-fastblock/meeting.rs').read_text()
start=source.index('    let reciprocal = if n > 1')
stop=source.index('\n\n    // Thread i',start)
snippet=source[start:stop]
rust='''
fn candidate(n: usize, threads: usize, u: u32) -> usize {
''' + snippet + '''
    block(u)
}
fn check(n:usize,t:usize,u:usize,count:&mut u64) {
    assert!(n>=1 && n<=1_740_512 && t>=1 && u<n);
    let x=(u as u128)*(t as u128);
    if x>u64::MAX as u128 { return; }
    let got=candidate(n,t,u as u32) as u128;
    let want=x/(n as u128);
    assert_eq!(got,want,"n={n} t={t} u={u} x={x}");
    *count+=1;
}
fn next(r:&mut u64)->u64 { *r^=*r<<13; *r^=*r>>7; *r^=*r<<17; *r }
fn main(){
    let mut count=0;
    for n in 1..=256 { for t in 1..=128 { for u in 0..n { check(n,t,u,&mut count); } } }
    let ns=[1usize,2,3,7,31,63,64,65,255,256,257,999,1000,65535,65536,1_000_000,1_740_511,1_740_512];
    let ts=[1usize,2,3,7,12,32,64,127,128,65535,1<<20,1<<32,usize::MAX/1_740_512,usize::MAX/2,usize::MAX];
    for n in ns { for t in ts {
        for u in [0,1,n/2,n.saturating_sub(2),n-1] { if u<n { check(n,t,u,&mut count); } }
        for k in [0usize,1,2,t/2,t.saturating_sub(2),t.saturating_sub(1),t] {
            let prod=(k as u128)*(n as u128);
            let point=prod.div_ceil(t as u128);
            for u in [point.saturating_sub(1),point,point+1] {if u<n as u128 {check(n,t,u as usize,&mut count);}}
        }
    }}
    let mut r=0x9e3779b97f4a7c15;
    for _ in 0..2_000_000 {
        let n=1+(next(&mut r)%1_740_512) as usize;
        let u=(next(&mut r)%n as u64) as usize;
        let t=1+(next(&mut r)%(u64::MAX/(u as u64).max(1)).max(1)) as usize;
        check(n,t,u,&mut count);
    }
    println!("PASS {count} exact block mappings (checked arithmetic)");
}
'''
with tempfile.TemporaryDirectory(prefix='d-recip-review-') as temp:
    p=Path(temp)/'check.rs'; p.write_text(rust)
    binary=str(Path(temp)/'check')
    subprocess.run(['rustc','--edition=2021','-C','opt-level=2','-C','overflow-checks=yes',str(p),'-o',binary],check=True)
    subprocess.run([binary],check=True)

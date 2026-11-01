#!/usr/bin/env python3
"""Compile exact summary loops with overflow checks and compare to bit enumeration."""
from pathlib import Path
import os
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
base = (ROOT/'experiments/b-opt9/baseline.rs').read_text()
start_marker = '    let (mut n, mut sum) = (0, 0);\n    for (i, &x) in bm.iter().enumerate() {'
end_marker = '    let ids = bm.iter().enumerate().filter'
start, end = base.index(start_marker), base.index(end_marker)
variants = [('baseline', ROOT/'experiments/b-opt9/baseline.rs')]
variants += [('zero', HERE/'candidate.rs')]
functions=[]
for name, path in variants:
    src=path.read_text()
    a,b=src.index(start_marker),src.index(end_marker)
    assert src[:a] == base[:start], (name,'prefix changed')
    assert src[b:] == base[end:], (name,'lazy first-ten or other suffix changed')
    functions.append(f'fn {name}(bm: &[u64]) -> (usize,u64) {{\n'+src[a:b]+'    (n,sum)\n}\n')
program = '\n'.join(functions)+r'''
const FUNCS: [fn(&[u64])->(usize,u64);2] = [baseline,zero];
fn expected(words: &[u64])->(usize,u64) {
    let (mut count,mut sum)=(0usize,0u64);
    for (i,&word) in words.iter().enumerate() {
        let mut x=word;
        while x!=0 {
            count+=1;
            sum+=(64*i) as u64+x.trailing_zeros() as u64;
            x&=x-1;
        }
    }
    (count,sum)
}
fn check(words:&[u64]) {
    let want=expected(words);
    for (i,f) in FUNCS.iter().enumerate() {assert_eq!(f(words),want,"variant {}",i);}
}
#[test]
fn exhaustive_16_bit_patterns() {
    for shift in [0,16,32,48] {
        for mask in 0..=65535u64 {check(&[0,mask<<shift,0]);}
    }
}
#[test]
fn threshold_and_full_local_id_edges() {
    check(&[]);check(&[0]);check(&[u64::MAX]);
    for n in 0..=64 {
        let mask=if n==64 {u64::MAX} else {(1u64<<n)-1};
        for shift in 0..64 {check(&[0,mask.rotate_left(shift),0]);}
    }
    let full=vec![u64::MAX;1024];
    assert_eq!(expected(&full),(65536,65536u64*65535/2));
    check(&full);
    let mut edge=vec![0;1024];edge[0]=1;edge[1023]=1<<63;check(&edge);
}
#[test]
fn mixed_random_multiword_sets() {
    let mut seed=0x7059_2026_1184_2631u64;
    for case in 0..10000 {
        let mut words=Vec::new();
        for i in 0..(case%65) {
            seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;
            let x=match (case+i)%7 {
                0=>0,1=>1<<(seed%64),2=>(1<<(seed%64))|(1<<((seed>>8)%64)),
                3=>(seed&0xffff).rotate_left((seed>>32) as u32),4=>u64::MAX,
                5=>seed&seed.rotate_left(13)&seed.rotate_left(39),_=>seed,
            };
            words.push(x);
        }
        check(&words);
    }
}
'''
with tempfile.TemporaryDirectory(prefix='b-opt9-bitmap-summary-') as td:
    p=Path(td);src=p/'property.rs';binary=p/'property';src.write_text(program)
    subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','--crate-name','bitmap_summary_property','--test','-Copt-level=2','-Coverflow-checks=yes','-Cdebug-assertions=yes',str(src),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
print('Exact candidate prefixes and lazy first-ten suffixes unchanged; both summary loops agree.')

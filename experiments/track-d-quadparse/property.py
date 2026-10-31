#!/usr/bin/env python3
"""Test the exact candidate decimal parser over digit widths and boundaries."""
import pathlib, subprocess, tempfile
s=pathlib.Path(__file__).with_name('meeting.rs').read_text()
start=s.index('#[inline]\nfn quad_number(');end=s.index('/// An edge as parsed:',start)
unit=r'''
#[test]
fn decimal_fields() {
    let mut vals = vec![0u32, 1, 9, 10, 99, 100, 999, 1000, 9999, 10000,
        99999, 100000, 999999, 1000000, 9999999, 10000000, 99999999,
        100000000, 999999999, 1000000000, u32::MAX - 1, u32::MAX];
    let mut seed=0x4d595df4d0f33173u64;
    for _ in 0..200000 { seed=seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407); vals.push((seed>>32) as u32); }
    for &v in &vals {
        let t = v.to_string();
        for suffix in ["", " ", "\n", " 0", "\n0"] {
            let s = format!("{t}{suffix}"); let mut p=0; assert_eq!(quad_number(s.as_bytes(),&mut p),v);
            assert_eq!(p, t.len() + usize::from(!suffix.is_empty()));
        }
    }
    let text=vals.iter().enumerate().map(|(i,v)|format!("{v}{}", if i%2==0 {" "} else {"\n"})).collect::<String>();
    let mut p=0; for &v in &vals { assert_eq!(quad_number(text.as_bytes(),&mut p),v); }
    assert_eq!(p,text.len());
}
'''
with tempfile.TemporaryDirectory(prefix='quad-prop-') as t:
 p=pathlib.Path(t); (p/'test.rs').write_text(s[start:end]+unit)
 subprocess.run(['rustc','--edition=2021','--test','-C','overflow-checks=yes',str(p/'test.rs'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)

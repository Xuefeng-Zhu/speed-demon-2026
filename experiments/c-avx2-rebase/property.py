#!/usr/bin/env python3
"""Compile the exact candidate delimiter function and compare with scalar search."""
from pathlib import Path
import subprocess
import sys
import platform
import tempfile

src = (Path(__file__).parent / 'candidate.rs').read_text()
start = src.index('fn field_delim(')
end = src.index('\n}\n', start) + 2
fn = src[start:end]
if '--avx2' in sys.argv:
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        raise SystemExit('--avx2 requires an x86-64 host')
    if sys.platform.startswith('linux') and 'avx2' not in Path('/proc/cpuinfo').read_text().lower().split():
        raise SystemExit('AVX2 is not advertised by this Linux host')
    fn_guard = '#[cfg(not(all(target_arch="x86_64", target_feature="avx2")))] compile_error!("AVX2 path not enabled");\n'
else:
    fn_guard = ''
main = r'''
fn main() {
    let mut seed = 0x6a09e667f3bcc909u64;
    let mut cases = 0u64;
    for len in 1..=256usize {
        for target in [0u8, 34, 44, 127, 255] {
            for at in 0..len {
                let mut b = vec![target.wrapping_add(1);len];
                b[at] = target;
                for start in 0..=at { assert_eq!(field_delim(&b,start,target), at); cases+=1; }
            }
        }
    }
    for _ in 0..1_000_000 {
        seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
        let len = (seed as usize % 511) + 1;
        let mut b = vec![0u8;len];
        for x in &mut b { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; *x = seed as u8; }
        seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
        let start = seed as usize % len;
        let target = b[start + ((seed >> 16) as usize % (len - start))];
        let expected = start + b[start..].iter().position(|&x| x == target).unwrap();
        assert_eq!(field_delim(&b,start,target),expected);
        cases += 1;
    }
    println!("{cases} delimiter comparisons passed");
}
'''
with tempfile.TemporaryDirectory(prefix='c-swar-property-') as td:
    t = Path(td); (t/'main.rs').write_text(fn_guard + fn + '\n' + main)
    subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes']+(['-C','target-feature=+avx2'] if '--avx2' in sys.argv else [])+[str(t/'main.rs'),'-o',str(t/'property')],check=True)
    subprocess.run([str(t/'property')],check=True)

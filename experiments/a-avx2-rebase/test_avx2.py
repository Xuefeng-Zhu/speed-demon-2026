#!/usr/bin/env python3
"""Compile the candidate's actual AVX2 function and compare it with its scalar fallback.
Linux x86-64 only. Inputs are placed across page boundaries and next to guard pages.
"""
import argparse
import pathlib
import platform
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--source', type=pathlib.Path, default=pathlib.Path(__file__).with_name('candidate.rs'))
args = p.parse_args()
if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
    raise SystemExit('Linux x86-64 with AVX2 required')
if 'avx2' not in pathlib.Path('/proc/cpuinfo').read_text().lower():
    raise SystemExit('AVX2 unavailable')
s = args.source.read_text()
helpers = s[s.index('/// Little-endian 8-byte load.'):s.index('/// Whether the `len` bytes')]
a = s.index('#[cfg(not(target_arch = "x86_64"))]\n#[inline]\nfn endpoint')
b = s.index('#[cfg(target_arch = "x86_64")]\n#[target_feature(enable = "avx2")]', a)
c = s.index('\nfn parse(', b)
scalar = s[a:b].replace('#[cfg(not(target_arch = "x86_64"))]\n', '').replace('fn endpoint(', 'fn scalar_endpoint(', 1)
vector = s[b:c]
main = r'''
use std::ffi::c_void;
const PAGE: usize = 4096;
extern "C" {
    fn mmap(a:*mut c_void,n:usize,prot:i32,flags:i32,fd:i32,off:i64)->*mut c_void;
    fn mprotect(a:*mut c_void,n:usize,prot:i32)->i32;
    fn munmap(a:*mut c_void,n:usize)->i32;
}
fn main() { unsafe {
    let p = mmap(std::ptr::null_mut(), PAGE*4, 0, 2|0x20, -1, 0);
    assert_ne!(p as isize, -1);
    let body = (p as *mut u8).add(PAGE);
    assert_eq!(mprotect(body.cast(), PAGE*2, 1|2), 0);
    let d = std::slice::from_raw_parts_mut(body, PAGE*2);
    let mut tests = 0usize;
    for n in 1..=125usize {
        for alignment in 0..32usize {
            for region in 0..2 {
                d.fill(b'X');
                // Interior crosses the physical page boundary for suitable lengths;
                // tail stops 32+alignment bytes before the inaccessible guard.
                let start = if region == 0 { PAGE - 64 + alignment }
                            else { PAGE*2 - 32 - alignment - n };
                for j in 0..n { d[start+j] = if j==0 {b'/'} else {b'a'+((j*17+n)%26) as u8}; }
                d[start+n]=b' ';
                let expected=scalar_endpoint(d,start);
                let got=endpoint(d,start);
                assert_eq!(got, expected, "n={n} align={alignment} region={region}");
                assert_eq!(got.0, start+n);
                tests+=1;
            }
        }
    }
    assert_eq!(munmap(p, PAGE*4),0);
    println!("PASS {tests} AVX2/scalar endpoint lengths, alignments and guard-page layouts");
}}
'''
with tempfile.TemporaryDirectory(prefix='a-avx2-guard-') as td:
    src = pathlib.Path(td) / 'test.rs'; out = pathlib.Path(td) / 'test'
    src.write_text('const ONES:u64=0x0101010101010101;\nconst MIX:u64=0x9E3779B97F4A7C15;\n' + helpers + scalar + vector + main)
    subprocess.run(['rustc','--edition=2021','-O','-C','target-cpu=x86-64-v3',str(src),'-o',str(out)],check=True)
    subprocess.run([str(out)],check=True)

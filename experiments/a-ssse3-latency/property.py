#!/usr/bin/env python3
"""Compile exact candidate latency parser; exercise all 0..9,999,999, u32 edges and page guards."""
from pathlib import Path
import platform, subprocess, tempfile
s=(Path(__file__).parent/'candidate.rs').read_text()
a=s.index('/// Little-endian 8-byte load.'); b=s.index('#[derive(Default)]',a)
body='const ONES: u64 = 0x0101_0101_0101_0101;\n'+s[a:b]
main=r'''
use std::ffi::c_void;
unsafe extern "C" {fn mmap(a:*mut c_void,n:usize,p:i32,f:i32,fd:i32,o:i64)->*mut c_void;fn mprotect(a:*mut c_void,n:usize,p:i32)->i32;fn munmap(a:*mut c_void,n:usize)->i32;fn getpagesize()->i32;}
fn fill(mut n:u32, b:&mut[u8])->usize {
 let mut tmp=[0u8;10];let mut k=0;
 loop{tmp[k]=(n%10) as u8+b'0';k+=1;n/=10;if n==0{break}}
 for i in 0..k {b[i]=tmp[k-1-i]};b[k]=b'\n';k
}
fn main() {
 let mut b=[0xa5u8; 32]; let mut checks=0u64;
 for n in 0..10_000_000u32 { let k=fill(n,&mut b);let (v,end)=parse_latency(&b,0);assert_eq!((v,end),(n as u64,k+1),"{n}");checks+=1; }
 let mut seed=0x123456789abcdef0u64;
 for _ in 0..1_000_000 {seed^=seed<<13;seed^=seed>>7;seed^=seed<<17;let n=seed as u32;let off=(seed>>32) as usize%16;let k=fill(n,&mut b[off..]);let (v,end)=parse_latency(&b,off);assert_eq!((v,end),(n as u64,off+k+1));checks+=1;}
 for n in [0,1,9,10,99,100,999,1_000,9_999,10_000,99_999,100_000,999_999,1_000_000,9_999_999,10_000_000,99_999_999,100_000_000,u32::MAX] {let k=fill(n,&mut b);assert_eq!(parse_latency(&b,0),(n as u64,k+1));checks+=1;}
 unsafe {
  let pg=getpagesize() as usize;
  #[cfg(target_os="macos")] let anon=0x1000;
  #[cfg(not(target_os="macos"))] let anon=0x20;
  let m=mmap(std::ptr::null_mut(),pg*2,3,2|anon,-1,0) as *mut u8;
  assert_ne!(m as isize,-1); assert_eq!(mprotect(m.add(pg).cast(),pg,0),0);
  for len in 8..=32 {let p=m.add(pg-len);for n in [0u32,1,9,10,999,100_000,9_999_999,u32::MAX] {let mut tmp=[0xa5;16];let k=fill(n,&mut tmp);if k+1<=len {std::ptr::write_bytes(p,b'9',len);std::ptr::copy_nonoverlapping(tmp.as_ptr(),p,k+1);let d=std::slice::from_raw_parts(p,len);assert_eq!(parse_latency(d,0),(n as u64,k+1));checks+=1;}} }
  assert_eq!(munmap(m.cast(),pg*2),0);
 }
 println!("PASS {checks} exact latency and guard checks");
}
'''
with tempfile.TemporaryDirectory(prefix='a-ssse3-property-') as td:
 p=Path(td); (p/'main.rs').write_text(body+main)
 flags=['rustc','--edition=2021','-O','-C','overflow-checks=no','-Awarnings']
 if platform.machine().lower() in ('x86_64','amd64'): flags+=['-C','target-feature=+ssse3']
 subprocess.run(flags+[str(p/'main.rs'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)

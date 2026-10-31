#!/usr/bin/env python3
from pathlib import Path
import subprocess,tempfile
s=(Path(__file__).parent/'candidate.rs').read_text()
def f(name):
 i=s.index('fn '+name+'(');return s[i:s.index('\n}\n',i)+2]
main=r'''
use std::ffi::c_void;
unsafe extern "C" { fn mmap(a:*mut c_void,n:usize,prot:i32,flags:i32,fd:i32,off:i64)->*mut c_void; fn mprotect(a:*mut c_void,n:usize,prot:i32)->i32; fn munmap(a:*mut c_void,n:usize)->i32; fn getpagesize()->i32; }
fn main(){ unsafe {
 let pg=getpagesize() as usize;
 #[cfg(target_os="macos")] let anon=0x1000;
 #[cfg(not(target_os="macos"))] let anon=0x20;
 let m=mmap(std::ptr::null_mut(),2*pg,3,2|anon,-1,0) as *mut u8;
 assert_ne!(m as isize,-1);assert_eq!(mprotect(m.add(pg).cast(),pg,0),0);
 let mut checks=0;
 for len in 2..=9 {
    let p=m.add(pg-len);std::ptr::write_bytes(p,b'1',len);*p.add(len-1)=b',';
    let b=std::slice::from_raw_parts(p,len);
    for start in 0..len-1 { let (mut i,mut j)=(start,start);let v=positive_fast(b,&mut i);let z=number(b,&mut j);assert_eq!((v,i),(z,j));checks+=1; }
 }
 assert_eq!(munmap(m.cast(),pg*2),0);println!("PASS {checks} guard-page comparisons");
}}
'''
with tempfile.TemporaryDirectory(prefix='c-swar-int-guard-') as td:
 p=Path(td);(p/'main.rs').write_text(f('number')+'\n'+f('positive_fast')+'\n'+main)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(p/'main.rs'),'-o',str(p/'main')],check=True);subprocess.run([str(p/'main')],check=True)

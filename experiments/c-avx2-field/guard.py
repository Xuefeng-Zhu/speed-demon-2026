#!/usr/bin/env python3
"""Exercise the actual delimiter finder against a PROT_NONE page boundary."""
from pathlib import Path
import subprocess
import sys
import platform
import tempfile
s=(Path(__file__).parent/('hybrid.rs' if '--hybrid' in sys.argv else 'candidate.rs')).read_text()
i=s.index('fn field_delim('); j=s.index('\n}\n', i)+2
body=s[i:j]
if '--avx2' in sys.argv:
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        raise SystemExit('--avx2 requires an x86-64 host')
    if sys.platform.startswith('linux') and 'avx2' not in Path('/proc/cpuinfo').read_text().lower().split():
        raise SystemExit('AVX2 is not advertised by this Linux host')
    fn_guard = '#[cfg(not(all(target_arch="x86_64", target_feature="avx2")))] compile_error!("AVX2 path not enabled");\n'
else:
    fn_guard = ''
main=r'''
use std::ffi::c_void;
unsafe extern "C" {
    fn mmap(a:*mut c_void,n:usize,prot:i32,flags:i32,fd:i32,off:i64)->*mut c_void;
    fn mprotect(a:*mut c_void,n:usize,prot:i32)->i32;
    fn munmap(a:*mut c_void,n:usize)->i32;
    fn getpagesize()->i32;
}
fn main() { unsafe {
    let pg=getpagesize() as usize;
    #[cfg(target_os="macos")] let anon=0x1000;
    #[cfg(not(target_os="macos"))] let anon=0x20;
    let m=mmap(std::ptr::null_mut(),pg*2,3,2|anon,-1,0) as *mut u8;
    assert_ne!(m as isize,-1); assert_eq!(mprotect(m.add(pg).cast(),pg,0),0);
    let mut lens:Vec<usize>=(1..=256.min(pg)).collect();
    for x in [511,512,1023,1024,4095,4096,8191,8192,pg] { if x<=pg && x>0 {lens.push(x);} }
    let mut checks=0;
    for len in lens {
        let ptr=m.add(pg-len);
        std::ptr::write_bytes(ptr,0x41,len); *ptr.add(len-1)=b'"';
        let b=std::slice::from_raw_parts(ptr,len);
        for start in 0..len {assert_eq!(field_delim(b,start,b'"'),len-1);checks+=1;}
    }
    assert_eq!(munmap(m.cast(),pg*2),0); println!("PASS {checks} guard-page comparisons");
}}
'''
with tempfile.TemporaryDirectory(prefix='c-swar-guard-') as td:
    p=Path(td);(p/'main.rs').write_text(fn_guard + body+'\n'+main)
    subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes']+(['-C','target-feature=+avx2'] if '--avx2' in sys.argv else [])+[str(p/'main.rs'),'-o',str(p/'main')],check=True)
    subprocess.run([str(p/'main')],check=True)

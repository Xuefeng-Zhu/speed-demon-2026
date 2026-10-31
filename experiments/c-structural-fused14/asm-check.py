#!/usr/bin/env python3
"""Optional codegen check only; it does not execute the x86 path."""
from pathlib import Path
import subprocess,tempfile
p=Path(__file__).resolve().parent
s=(p/'candidate.rs').read_text();start=s.index('#[inline(always)]\nfn structural_scalar');end=s.index('/// Strip only valid outer quotes',start)
body=s[start:end]
wrapper='''\n#[no_mangle]\npub unsafe extern "C" fn check_structural(ptr:*const u8,carry:bool)->u64 {\n let s=unsafe{std::slice::from_raw_parts(ptr,32)};\n let(q,d,c)=unsafe{structural_avx2(s,carry)};\n (q as u64)^((d as u64)<<32)^((c as u64)<<63)\n}\n'''
with tempfile.TemporaryDirectory(prefix='c-structural-asm-') as d:
 t=Path(d);src=t/'check.rs';asm=t/'check.s';src.write_text('#![crate_type="lib"]\n'+body+wrapper)
 subprocess.run(['rustc','--edition=2021','-O','--target','x86_64-pc-windows-msvc','-C','target-cpu=x86-64-v3','--emit=asm',str(src),'-o',str(asm)],check=True)
 s=asm.read_text().lower();assert 'vpmovmskb' in s and 'vpcmpeqb' in s
 print('PASS x86-v3 code generation contains AVX2 compare/movemask; this did NOT execute x86')

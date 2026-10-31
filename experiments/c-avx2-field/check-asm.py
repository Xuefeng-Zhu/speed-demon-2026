#!/usr/bin/env python3
"""Extract candidate helper, compile optimized x86-64-v3 assembly, print AVX2 opcodes."""
import argparse, re, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--target');a=p.parse_args()
s=a.source.read_text();i=s.index('fn field_delim(');j=s.index('\n}\n',i)+2
with tempfile.TemporaryDirectory(prefix='c-avx-asm-') as td:
 d=Path(td); src=d/'check.rs';asm=d/'check.s'
 src.write_text(s[i:j]+'\n#[unsafe(no_mangle)] pub fn probe(b:&[u8],i:usize,c:u8)->usize{field_delim(b,i,c)}\n')
 cmd=['rustc','--edition=2021','-C','target-cpu=x86-64-v3','-O','--crate-type=lib','--emit=asm','-Awarnings']
 if a.target:cmd+=['--target',a.target]
 subprocess.run(cmd+[str(src),'-o',str(asm)],check=True)
 lines=asm.read_text().splitlines();hits=[x.strip() for x in lines if re.search(r'vpcmpeqb|vpmovmskb|vpbroadcastb',x)]
 assert hits and any('vpcmpeqb' in x for x in hits) and any('vpmovmskb' in x for x in hits)
 print('\n'.join(hits))

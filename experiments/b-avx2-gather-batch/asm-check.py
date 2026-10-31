#!/usr/bin/env python3
"""Compile the exact gather helper to Windows x86 assembly; never execute it."""
import subprocess
import tempfile
from pathlib import Path

source = (Path(__file__).parent / 'candidate.rs').read_text()
start = source.index('unsafe fn gather_initial(')
end = source.index('\nimpl WordBatch', start)
helper = source[start:end]
prefix = '''#![allow(dead_code)]
const MISS: u32 = u32::MAX;
#[derive(Clone, Copy)]
#[repr(align(32))]
pub struct Key([u64; 4]);
'''
wrapper = '''
#[no_mangle]
pub unsafe extern "C" fn probe(slots: *const u32, keys: *const Key, out: *mut u64) {
    let (ids, vals) = gather_initial(std::slice::from_raw_parts(slots, 4),
        std::slice::from_raw_parts(keys, 4), [0, 1, 2, 3], [true; 4]);
    std::ptr::copy_nonoverlapping(ids.as_ptr(), out.cast::<u32>(), 4);
    std::ptr::copy_nonoverlapping(vals.as_ptr(), out.add(2), 4);
}
'''
with tempfile.TemporaryDirectory(prefix='b-gather-asm-') as tmp:
    path = Path(tmp) / 'helper.rs'; asm = Path(tmp) / 'helper.s'
    path.write_text(prefix + helper + wrapper)
    subprocess.run(['rustc', '--edition=2021', '-O', '--crate-type=lib',
                    '--target=x86_64-pc-windows-msvc', '-C', 'target-cpu=x86-64-v3',
                    '--emit=asm', str(path), '-o', str(asm)], check=True)
    code = asm.read_text().lower()
    if 'vpgatherdd' not in code or 'vpgatherdq' not in code:
        raise SystemExit('expected gather instructions not found')
    print('PASS representative x86 codegen: vpgatherdd and vpgatherdq; not executed')

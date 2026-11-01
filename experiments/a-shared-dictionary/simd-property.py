#!/usr/bin/env python3
"""Exercise the exact rebased SSSE3 parser on native x86-64 Linux; no timing claims.

Run under the same pinned native x86 Rust tool image used for the comparison:
    python3 experiments/a-shared-dictionary/simd-property.py

Compiles only the actual source's load, zero-byte, delimiter and latency helpers.
Checks every 1--7-digit value, random u32 values/alignments, decimal boundaries,
and readable spans immediately before a protected page. Uses a disposable folder.
"""

import hashlib
import platform
import subprocess
import tempfile
from pathlib import Path


def extract_function(source, name):
    declaration = source.index(f"fn {name}(")
    start = source.rfind("#[inline(always)]", 0, declaration)
    opening = source.index("{", declaration)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


def main():
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise SystemExit("requires native Linux x86-64 with x86-64-v3 CPU features")
    features = Path("/proc/cpuinfo").read_text().lower().split()
    if "ssse3" not in features or "avx2" not in features:
        raise SystemExit("CPU must report SSSE3 and AVX2")
    path = Path(__file__).with_name("simd.rs")
    source = path.read_text()
    assert "_mm_maddubs_epi16" in source and "_mm_madd_epi16" in source
    body = "const ONES: u64 = 0x0101_0101_0101_0101;\n"
    body += "\n".join(extract_function(source, name) for name in
                      ("load", "zero_bytes", "find_byte", "parse_latency"))
    harness = r'''
use std::ffi::c_void;
extern "C" {
    fn mmap(a: *mut c_void, n: usize, p: i32, f: i32, fd: i32, o: i64) -> *mut c_void;
    fn mprotect(a: *mut c_void, n: usize, p: i32) -> i32;
    fn munmap(a: *mut c_void, n: usize) -> i32;
    fn getpagesize() -> i32;
}
fn fill(mut n: u32, b: &mut [u8]) -> usize {
    let mut tmp = [0u8; 10];
    let mut k = 0;
    loop {
        tmp[k] = (n % 10) as u8 + b'0';
        k += 1;
        n /= 10;
        if n == 0 { break; }
    }
    for i in 0..k { b[i] = tmp[k - 1 - i]; }
    b[k] = b'\n';
    k
}
fn main() {
    let mut bytes = [0xa5u8; 32];
    let mut checks = 0u64;
    for n in 0..10_000_000u32 {
        let digits = fill(n, &mut bytes);
        assert_eq!(parse_latency(&bytes, 0), (n as u64, digits + 1), "n={n}");
        checks += 1;
    }
    let mut seed = 0x1234_5678_9abc_def0u64;
    for _ in 0..1_000_000 {
        seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17;
        let (n, offset) = (seed as u32, (seed >> 32) as usize % 16);
        let digits = fill(n, &mut bytes[offset..]);
        assert_eq!(parse_latency(&bytes, offset), (n as u64, offset + digits + 1));
        checks += 1;
    }
    let edges = [0u32, 1, 9, 10, 99, 100, 999, 1_000, 9_999, 10_000, 99_999,
                 100_000, 999_999, 1_000_000, 9_999_999, 10_000_000, 99_999_999,
                 100_000_000, 999_999_999, 1_000_000_000, u32::MAX];
    for n in edges {
        for offset in 0..16 {
            let digits = fill(n, &mut bytes[offset..]);
            assert_eq!(parse_latency(&bytes, offset), (n as u64, offset + digits + 1));
            checks += 1;
        }
    }
    unsafe {
        let page = getpagesize() as usize;
        let mapping = mmap(std::ptr::null_mut(), page * 2, 3, 2 | 0x20, -1, 0) as *mut u8;
        assert_ne!(mapping as isize, -1);
        assert_eq!(mprotect(mapping.add(page).cast(), page, 0), 0);
        for len in 8..=32 {
            let start = mapping.add(page - len);
            for n in edges {
                let mut text = [0xa5u8; 16];
                let digits = fill(n, &mut text);
                if digits + 1 <= len {
                    std::ptr::write_bytes(start, b'9', len);
                    std::ptr::copy_nonoverlapping(text.as_ptr(), start, digits + 1);
                    let readable = std::slice::from_raw_parts(start, len);
                    assert_eq!(parse_latency(readable, 0), (n as u64, digits + 1));
                    checks += 1;
                }
            }
        }
        assert_eq!(munmap(mapping.cast(), page * 2), 0);
    }
    println!("PASS {checks} exact SSSE3/fallback value, alignment and guard checks");
}
'''
    print(f"source_sha256={hashlib.sha256(source.encode()).hexdigest()}", flush=True)
    flags = ["--edition=2021", "-C", "opt-level=3", "-C", "lto=fat", "-C",
             "codegen-units=1", "-C", "panic=abort", "-C", "overflow-checks=yes",
             "-C", "target-cpu=x86-64-v3"]
    with tempfile.TemporaryDirectory(prefix="a-simd-property-") as directory:
        temporary = Path(directory)
        program, binary = temporary / "main.rs", temporary / "property"
        program.write_text(body + harness)
        subprocess.run(["rustc", *flags, str(program), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()

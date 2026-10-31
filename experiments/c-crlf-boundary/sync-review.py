#!/usr/bin/env python3
"""Compile exact candidate sync_crlf and assert record-boundary cuts."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
args = parser.parse_args()
source = args.source.read_text()
assert source.count('fn main() {') == 1
source = source.replace('fn main() {', 'fn original_main() {', 1)
source += r'''
fn main() {
    let mut state = 0x42c0ffee1234u64;
    let mut checks = 0u64;
    for case in 0..500 {
        let mut b = b"\xef\xbb\xbfid,name,note,region_id,amount\r\n".to_vec();
        let start = b.len();
        let mut valid = vec![start];
        for id in 1..=1+(case%37) {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let n = (state as usize >> 24) % 250;
            if id % 4 == 0 { b.extend_from_slice(b"\xef\xbb\xbf"); }
            b.extend_from_slice(id.to_string().as_bytes());
            b.extend_from_slice(b",\"a\",\"start\nmid \"\"quote\"\" ");
            b.extend(std::iter::repeat(b'x').take(n));
            b.extend_from_slice(b"\nend\",1,-0.05");
            if id==1+(case%37) || state & 3 == 0 { b.extend_from_slice(b"\r\n"); } else { b.push(b'\n'); }
            valid.push(b.len());
        }
        let mut previous = start;
        for p in start..=b.len() {
            let at = sync_crlf(&b,p);
            assert!(at >= p && at <= b.len() && at >= previous, "case {case} p {p} at {at} prev {previous}");
            assert!(valid.contains(&at), "case {case} cut {p} returned non-record-boundary {at}");
            previous = at; checks += 1;
        }
    }
    println!("PASS {checks} exact-source sync cuts over 500 generated fixtures");
}
'''
with tempfile.TemporaryDirectory(prefix='c-crlf-sync-review-') as tmp:
    source_path = Path(tmp) / 'review.rs'
    binary = Path(tmp) / 'review'
    source_path.write_text(source)
    subprocess.run(['rustc', '--edition=2021', '-O', '-Awarnings', str(source_path), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

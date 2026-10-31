#!/usr/bin/env python3
"""Ensure the x86 property test exercises the exact candidate classifier."""
from pathlib import Path

root = Path(__file__).resolve().parent
candidate = (root / 'candidate.rs').read_text()
test = (root / 'classifier-property.rs').read_text()
needle = '#[target_feature(enable = "avx2")]'
a = candidate[candidate.index(needle):candidate.index('\n#[inline]\nfn push_word')].strip()
b = test[test.index(needle):test.index('\n#[cfg(not(target_arch')].strip()
b = b.replace('pub unsafe fn classify_avx2', 'unsafe fn classify_avx2', 1)
if a != b:
    raise SystemExit('candidate and test classifiers differ')
print('PASS: exact AVX2 classifier matches property test')

#!/usr/bin/env python3
"""Prepare a synthetic repeated-fallback test from verified public sample 1.

Pass the sample data directory, a previously verified sample distances.txt, and
an output directory that does not already exist. No input files are changed.
"""
import hashlib
import os
from pathlib import Path
import sys

sample, sample_answers, dest = map(Path, sys.argv[1:4])
answer_bytes = sample_answers.read_bytes()
assert hashlib.sha256(answer_bytes).hexdigest() == 'a4c76ed030bc7e365db33191f6cf74708fba7f25eb48d64c8c4279f2e57046a0'
queries = (sample / 'queries.txt').read_text().splitlines()
answers = answer_bytes.decode('ascii').splitlines()
assert len(queries) == len(answers) == 200
indices = [9, 31, 158]  # observed to trigger fallback in instrumented seed-1 sample
picks = [indices[i % len(indices)] for i in range(2000)]
dest.mkdir(exist_ok=False)
os.link(sample / 'graph.txt', dest / 'graph.txt')
(dest / 'queries.txt').write_text(''.join(queries[i] + '\n' for i in picks))
expected = ''.join(answers[i] + '\n' for i in picks).encode('ascii')
digest = hashlib.sha256(expected).hexdigest()
assert digest == '0d05b38657900e99f9c4c5e96a5a570d76010c08caf5611cb13690c00f2124fe'
print(digest)

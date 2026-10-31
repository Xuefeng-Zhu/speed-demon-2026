#!/usr/bin/env python3
"""Summarize the recorded eight-worker official public seed-1 diagnostic."""
import ast
import json
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name('profile.log')).read_text().splitlines()
entries = []
for line in lines:
    match = re.match(r'B_ROLE lo=(\d+) hi=(\d+) tokens=(\[[^\]]*\]) docs=(\[[^\]]*\])', line)
    if match:
        lo, hi = map(int, match.group(1, 2))
        entries.append((lo, hi, ast.literal_eval(match.group(3)), ast.literal_eval(match.group(4))))

# The program performs a separate sample pass before its eight full-data passes.
# For this recorded seed, the sample is exactly [0, 524645). Do not use this
# script unmodified to identify the sample for another dataset or worker count.
entries = sorted(e for e in entries if (e[0], e[1]) != (0, 524645))
assert len(entries) == 8 and entries[0][0] == 0 and entries[-1][1] == 253827587
assert all(a[1] == b[0] for a, b in zip(entries, entries[1:]))
tokens = [sum(e[2][i] for e in entries) for i in range(5)]
doc_masks = [sum(e[3][i] for e in entries) for i in range(32)]
assert sum(tokens) == 36276657 and sum(doc_masks) == 250000
names = ['bool_only', 'anchor_only', 'both', 'phrase_nonanchor_only', 'miss']
counts = dict(zip(names, tokens))
docs = {name: sum(n for mask, n in enumerate(doc_masks) if mask & (1 << i)) for i, name in enumerate(names)}
print(json.dumps({'chunks': len(entries), 'input_bytes': entries[-1][1], 'documents': sum(doc_masks),
                  'tokens': sum(tokens), 'token_counts': counts, 'docs_with_category': docs}, indent=2))

#!/usr/bin/env python3
"""Independent low-memory spot oracle; this does not check every query."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--data', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--limit', type=int, default=64)
p.add_argument('--report', type=Path)
a = p.parse_args()
if a.limit < 1:
    p.error('--limit must be positive')
started = time.monotonic()
qbytes = (a.data / 'queries.txt').read_bytes()
lines = qbytes.splitlines()
output_bytes = a.output.read_bytes()
output = output_bytes.splitlines()
if output_bytes and not output_bytes.endswith(b'\n'):
    raise SystemExit('output is missing its trailing LF')
if len(output) != len(lines):
    raise SystemExit(f'query/output count mismatch: {len(lines)} versus {len(output)}')
queries = []
for line in lines:
    if line.startswith(b'BOOL '):
        terms = line[5:].split(b' ')
        queries.append((b'B', terms, (len(terms[::2]), tuple(terms[1::2]))))
    elif line.startswith(b'PHRASE "') and line.endswith(b'"'):
        terms = line[8:-1].split(b' ')
        queries.append((b'P', terms, len(terms)))
    else:
        raise SystemExit(f'bad query grammar: {line!r}')
# Prefer distinct query shapes, then deterministic coverage across the file.
first = {}
for i, (kind, _, shape) in enumerate(queries):
    first.setdefault((kind, shape), i)
mandatory = list(dict.fromkeys(next(i for i, q in enumerate(queries) if q[0] == kind) for kind in sorted({q[0] for q in queries})))
choices = [i for i in first.values() if i not in mandatory]
rng = random.Random(90210)
rng.shuffle(choices)
selected = (mandatory + choices)[:min(a.limit, len(lines))]
seen = set(selected)
remaining = [i for i in range(len(lines)) if i not in seen]
rng.shuffle(remaining)
selected += remaining[:min(a.limit, len(lines)) - len(selected)]
selected.sort()
counts = [0] * len(selected)
sums = [0] * len(selected)
tops = [[] for _ in selected]
pattern = re.compile(rb'[a-z0-9]+')
docs_sha = hashlib.sha256()
ndocs = 0
with (a.data / 'docs.txt').open('rb') as f:
    for line in f:
        docs_sha.update(line)
        doc_id, tab, text = line.partition(b'\t')
        if not tab or int(doc_id) != ndocs or not text.endswith(b'\n'):
            raise SystemExit(f'bad document boundary at line {ndocs}')
        tokens = pattern.findall(text[:-1].lower())
        present = set(tokens)
        for j, qi in enumerate(selected):
            kind, terms, _ = queries[qi]
            if kind == b'B':
                hit = terms[0] in present
                for op, term in zip(terms[1::2], terms[2::2]):
                    member = term in present
                    if op == b'AND':
                        hit = hit and member
                    elif op == b'OR':
                        hit = hit or member
                    elif op == b'NOT':
                        hit = hit and not member
                    else:
                        raise SystemExit(f'bad Boolean operator: {op!r}')
            else:
                hit = all(term in present for term in terms)
                if hit:
                    hit = any(tokens[k:k + len(terms)] == terms for k in range(len(tokens) - len(terms) + 1))
            if hit:
                counts[j] += 1
                sums[j] += ndocs
                if len(tops[j]) < 10:
                    tops[j].append(ndocs)
        ndocs += 1
for j, qi in enumerate(selected):
    expected = b' '.join(str(n).encode('ascii') for n in [counts[j], sums[j], *tops[j]])
    if output[qi] != expected:
        raise SystemExit(f'query {qi} mismatch: got {output[qi]!r}, expected {expected!r}')
report = {'passed': True, 'checked_queries': len(selected), 'all_queries': len(lines),
          'documents': ndocs, 'indices': selected, 'seconds': time.monotonic() - started,
          'docs_sha256': docs_sha.hexdigest(), 'queries_sha256': hashlib.sha256(qbytes).hexdigest(),
          'output_sha256': hashlib.sha256(output_bytes).hexdigest(),
          'scope': 'selected queries across every document, not full-output verification'}
if a.report:
    a.report.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))

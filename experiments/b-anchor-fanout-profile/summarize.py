#!/usr/bin/env python3
"""Aggregate diagnostic stderr. This is not a timing benchmark."""
import ast
import json
import re
import sys

lines = [line for line in open(sys.argv[1], encoding='utf-8') if line.startswith('ANCHOR_PROFILE ')]
if not lines:
    raise SystemExit('no ANCHOR_PROFILE lines')
keys = ['occ', 'comparisons', 'group_probes', 'static_anchors', 'static_phrases']
rows = []
for line in lines:
    m = re.search(r'first=(\d+) ndocs=(\d+)', line)
    if not m:
        raise SystemExit(f'malformed header: {line}')
    row = {'first': int(m.group(1)), 'ndocs': int(m.group(2))}
    for key in keys:
        m = re.search(rf'{key}=(\[[^\]]*\])', line)
        if not m:
            raise SystemExit(f'missing {key}: {line}')
        row[key] = ast.literal_eval(m.group(1))
        if len(row[key]) != 9 or any(not isinstance(n, int) or n < 0 for n in row[key]):
            raise SystemExit(f'bad histogram {key}: {line}')
    rows.append(row)
for k in ('static_anchors', 'static_phrases'):
    if any(r[k] != rows[0][k] for r in rows):
        raise SystemExit(f'{k} differs across chunks')
out = {'bins': ['1', '2', '3-4', '5-8', '9-16', '17-32', '33-64', '65-128', '129+'],
       'chunks': len(rows), 'documents': sum(r['ndocs'] for r in rows),
       'static_anchors': rows[0]['static_anchors'], 'static_phrases': rows[0]['static_phrases']}
for k in ('occ', 'comparisons', 'group_probes'):
    out[k] = [sum(r[k][i] for r in rows) for i in range(9)]
    out[k + '_total'] = sum(out[k])
print(json.dumps(out, indent=2))

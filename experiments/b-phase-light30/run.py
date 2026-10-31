#!/usr/bin/env python3
"""Run the phase diagnostic serially, verify every output, and retain raw timings."""
import argparse, hashlib, json, os, pathlib, statistics, subprocess, tempfile, time

p = argparse.ArgumentParser()
p.add_argument('--binary', required=True)
p.add_argument('--data', required=True)
p.add_argument('--runs', type=int, default=10)
p.add_argument('--report', required=True)
a = p.parse_args()
if a.runs < 1:
    p.error('--runs must be positive')
expected = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
rows = []
with tempfile.TemporaryDirectory(prefix='sd-b-phase30-') as out:
    for run in range(-1, a.runs):
        start = time.monotonic()
        process = subprocess.run([a.binary], env={**os.environ, 'SD_DATA': a.data, 'SD_OUT': out}, capture_output=True, text=True, check=True)
        wall = time.monotonic() - start
        digest = hashlib.sha256((pathlib.Path(out) / 'results.txt').read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError((run, digest))
        phases, indexes = {}, []
        for line in process.stderr.splitlines():
            x = line.split()
            if len(x) == 3 and x[0] == 'PHASE':
                if x[1] in phases: raise ValueError(('duplicate phase', line))
                phases[x[1]] = int(x[2]) / 1e9
            elif len(x) == 5 and x[0] == 'IDX':
                indexes.append({'lo': int(x[1]), 'ndocs': int(x[2]), 'scan_s': int(x[3])/1e9, 'total_s': int(x[4])/1e9})
            else:
                raise ValueError(('unexpected stderr', line))
        expected_phases = {'read_queries', 'query_plan', 'short_map', 'sample_anchor', 'index', 'freqs_cache', 'answer', 'output_format', 'output_write', 'total'}
        if set(phases) != expected_phases or not indexes:
            raise ValueError(('incomplete diagnostic', phases, indexes))
        rows.append({'run':run, 'warmup':run < 0, 'wall_s':wall, 'sha256':digest, 'phases':phases, 'indexes':indexes})
measured = [row for row in rows if not row['warmup']]
summary = {'median_wall_s': statistics.median(row['wall_s'] for row in measured),
           'median_phase_s': {k:statistics.median(row['phases'][k] for row in measured) for k in measured[0]['phases']},
           'median_index_worker_max_s': statistics.median(max(v['total_s'] for v in row['indexes']) for row in measured),
           'median_index_scan_worker_elapsed_sum_s': statistics.median(sum(v['scan_s'] for v in row['indexes']) for row in measured),
           'median_index_csr_worker_elapsed_sum_s': statistics.median(sum(v['total_s']-v['scan_s'] for v in row['indexes']) for row in measured)}
pathlib.Path(a.report).write_text(json.dumps({'summary':summary, 'runs':rows}, indent=2)+'\n')
print(json.dumps(summary, indent=2))

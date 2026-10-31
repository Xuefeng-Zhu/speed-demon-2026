#!/usr/bin/env python3
"""Run diagnostic candidate and check every output and requested counters."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ap = argparse.ArgumentParser()
ap.add_argument("--binary", type=Path, required=True)
ap.add_argument("--data", type=Path, required=True)
ap.add_argument("--shape", choices=["chain", "broad"], required=True)
ap.add_argument("--threads", type=int, default=12)
ap.add_argument("--min-wide-active", type=int, default=1)
ap.add_argument("--min-wide-runs", type=int, default=1)
ap.add_argument("--min-narrow-touch", type=int, default=0)
ap.add_argument("--min-wide-touch", type=int, default=0)
ap.add_argument("--barrier-at", type=int, default=0,
                help="hold each worker's first wide search at this touched count until all workers arrive")
ap.add_argument("--barrier-timeout", type=int, default=90, help="seconds before barrier aborts the diagnostic")
ap.add_argument("--timeout", type=float, default=300, help="kill the direct diagnostic child after this many seconds")
ap.add_argument("--require-cutoff", action="store_true")
ap.add_argument("--require-exhaustion", action="store_true")
a = ap.parse_args()
assert 1 <= a.threads <= 12 and a.barrier_at >= 0 and 1 <= a.barrier_timeout <= 300 and a.timeout > 0
with (a.data / "graph.txt").open() as f:
    n, _ = map(int, f.readline().split())
queries = [tuple(map(int, line.split())) for line in (a.data / "queries.txt").read_text().splitlines()]
assert all((s, t) == (0, n - 1) or s == t for s, t in queries), "unexpected generated query"
heavy_answer = (2**32 - 1 + n - 2) if a.shape == "chain" else 2
expected = ["0" if s == t else str(heavy_answer) for s, t in queries]
with tempfile.TemporaryDirectory(prefix="sd-hybrid-probe-") as tmp:
    out = Path(tmp)
    env = {**os.environ, "SD_DATA": str(a.data.resolve()), "SD_OUT": str(out),
           "SD_STRESS_THREADS": str(a.threads), "SD_STRESS_BARRIER_AT": str(a.barrier_at),
           "SD_STRESS_BARRIER_TIMEOUT_SECONDS": str(a.barrier_timeout)}
    try:
        r = subprocess.run([str(a.binary.resolve())], env=env, text=True, capture_output=True, timeout=a.timeout)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"SD_STRESS_PROCESS_TIMEOUT after {a.timeout} seconds")
    if r.returncode:
        raise SystemExit(f"diagnostic exited {r.returncode}: {r.stderr[-4000:]}")
    actual = (out / "distances.txt").read_text().splitlines()
    assert actual == expected, "one or more shortest-path outputs differ from the exact oracle"
    lines = [x for x in r.stderr.splitlines() if x.startswith("SD_STRESS_METRICS ")]
    assert len(lines) == 1, ("missing or duplicate metrics", r.stderr[-4000:])
    fields = dict((k, int(v)) for k, v in re.findall(r"([a-z_]+)=([0-9]+)", lines[0]))
    for k in ("narrow_touch_max", "wide_touch_max", "cutoff_queries", "pool_exhaust_queries", "wide_runs", "wide_active_max", "wide_barrier_arrived"):
        assert k in fields, (k, lines[0])
    assert fields["wide_runs"] >= a.min_wide_runs, fields
    assert fields["wide_active_max"] >= a.min_wide_active, fields
    assert fields["narrow_touch_max"] >= a.min_narrow_touch, fields
    assert fields["wide_touch_max"] >= a.min_wide_touch, fields
    if a.require_cutoff: assert fields["cutoff_queries"] > 0, fields
    if a.require_exhaustion: assert fields["pool_exhaust_queries"] > 0, fields
    if a.barrier_at:
        assert fields["wide_barrier_arrived"] == a.threads, fields
        assert fields["wide_active_max"] == a.threads, fields
    print(f"PASS {len(queries)} exact answers; {lines[0]}")

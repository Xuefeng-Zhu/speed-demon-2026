#!/usr/bin/env python3
"""Confirm an incomplete diagnostic barrier exits rather than hanging."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from generate import generate

ap = argparse.ArgumentParser()
ap.add_argument("--binary", type=Path, required=True)
a = ap.parse_args()
with tempfile.TemporaryDirectory(prefix="sd-barrier-timeout-") as d:
    root = Path(d)
    data, out = root / "data", root / "out"
    out.mkdir()
    # One nontrivial query cannot bring two workers to the barrier.
    generate(data, "chain", 101, 300, 2, 1)
    env = {**os.environ, "SD_DATA": str(data), "SD_OUT": str(out),
           "SD_STRESS_THREADS": "2", "SD_STRESS_BARRIER_AT": "100",
           "SD_STRESS_BARRIER_TIMEOUT_SECONDS": "1"}
    result = subprocess.run([str(a.binary.resolve())], env=env, text=True,
                            capture_output=True, timeout=8)
    assert result.returncode == 86 and "SD_STRESS_BARRIER_TIMEOUT" in result.stderr, (
        result.returncode, result.stderr)
    print("PASS bounded missing-participant barrier:", result.stderr.strip())

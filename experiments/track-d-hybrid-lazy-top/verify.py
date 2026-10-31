#!/usr/bin/env python3
"""Test exact hybrid lazy-top source at forced pool capacities."""
import hashlib
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
source = (HERE / "candidate.rs").read_text()
assert hashlib.sha256(source.encode()).hexdigest() == "50bd42988224e2d4ab34d024d2edd76813c6ccc7a5e6c6300139600f48a94932"
marker = "const POOL_CAP: usize = 65_536;"
assert source.count(marker) == 1

def run(*args):
    subprocess.run([str(a) for a in args], check=True)

with tempfile.TemporaryDirectory(prefix="sd-d-lazy-") as tmp:
    tmp = Path(tmp)
    tests = tmp / "tests.rs"
    tests.write_text(source + "\n" + (HERE / "property-tail.rs").read_text())
    test_bin = tmp / "tests"
    flags = ["rustc", "--edition=2021", "-O", "-C", "overflow-checks=yes", "-C", "debug-assertions=yes"]
    run(*flags, "--test", tests, "-o", test_bin)
    run(test_bin, "--test-threads=1")
    bins = []
    for cap in (0, 1, 2, 65_536):
        path = tmp / f"cap{cap}.rs"
        binary = tmp / f"cap{cap}"
        path.write_text(source.replace(marker, f"const POOL_CAP: usize = {cap};"))
        run(*flags, path, "-o", binary)
        bins.append(binary)
    for script in ("oracle.py", "exhaustive.py"):
        run("python3", ROOT / "experiments/track-d-balanced-frontier" / script, *bins)
    run("python3", ROOT / "experiments/track-d-u32-fallback/thresholds.py", *bins)
    for binary in (bins[1], bins[3]):
        run("python3", ROOT / "experiments/track-d-packed32-adj/boundaries.py", binary)
    run("python3", ROOT / "experiments/track-d-balanced-frontier/extremes.py", bins[1], bins[3])
print("PASS exact source, queue lower bounds, four capacities, graph and extreme tests")

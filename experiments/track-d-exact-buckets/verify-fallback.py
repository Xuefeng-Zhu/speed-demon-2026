#!/usr/bin/env python3
"""Check exact-bucket loader with forced search-queue fallback capacities."""
import hashlib
from pathlib import Path
import subprocess
import tempfile

here = Path(__file__).resolve().parent
root = here.parents[1]
source = (here / "candidate.rs").read_text()
assert hashlib.sha256(source.encode()).hexdigest() == "e4caa9848aadb4af327ef99cd00a2e8a0454c6ce28ea226c2485a84d44330e0e"
marker = "const POOL_CAP: usize = 65_536;"
assert source.count(marker) == 1
with tempfile.TemporaryDirectory(prefix="sd-exact-buckets-") as temporary:
    build = Path(temporary)
    binaries = []
    for cap in (0, 1, 2):
        src = build / f"cap{cap}.rs"
        binary = build / f"cap{cap}"
        src.write_text(source.replace(marker, f"const POOL_CAP: usize = {cap};"))
        subprocess.run(["rustc", "--edition=2021", "-O", "-C", "overflow-checks=yes", "-C", "debug-assertions=yes", str(src), "-o", str(binary)], check=True)
        binaries.append(str(binary))
    for test in ("track-d-balanced-frontier/oracle.py", "track-d-u32-fallback/thresholds.py"):
        subprocess.run(["python3", str(root / "experiments" / test), *binaries], check=True)

#!/usr/bin/env python3
"""Test frozen vector heap under default and deliberately tiny capacities."""
import hashlib
import subprocess
import tempfile
from pathlib import Path

here = Path(__file__).resolve().parent
source = here.parent / "track-d-capped-vector-buckets" / "candidate.rs"
raw = source.read_bytes()
expected = "3496a3a8e06f35e5effeb162735eef44dbb0728a44d487be2a9a951e8763160a"
assert hashlib.sha256(raw).hexdigest() == expected, "candidate changed"
text = raw.decode()
marker = "const POOL_CAP: usize = 65_536;"
assert text.count(marker) == 1
tail = (here / "test-tail.rs").read_text()
with tempfile.TemporaryDirectory(prefix="sd-vector-independent-") as tmp:
    tmp = Path(tmp)
    for cap in (0, 1, 2, 65536):
        src = tmp / f"cap{cap}.rs"
        binary = tmp / f"cap{cap}"
        src.write_text(text.replace(marker, f"const POOL_CAP: usize = {cap};") + "\n" + tail)
        subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C", "overflow-checks=yes",
                        "-C", "debug-assertions=yes", str(src), "-o", str(binary)], check=True)
        subprocess.run([str(binary), "--test-threads=1"], check=True)
print("PASS exact-source vector heap capacity and model tests")

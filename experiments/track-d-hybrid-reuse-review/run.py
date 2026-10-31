#!/usr/bin/env python3
"""Exercise repeated mixed fallback/fast-path sequences on the exact hybrid."""
from pathlib import Path
import hashlib
import subprocess
import tempfile

here = Path(__file__).resolve().parent
src = (here.parent / "track-d-capped-hybrid" / "candidate.rs").read_text()
assert hashlib.sha256(src.encode()).hexdigest() == "671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c"
tail = (here / "reuse-tail.rs").read_text()
marker = "const POOL_CAP: usize = 65_536;"
assert src.count(marker) == 1
with tempfile.TemporaryDirectory(prefix="sd-d-reuse-") as tmp:
    tmp = Path(tmp)
    for cap in (0, 1, 2, 7, 64, 65_536):
        test = tmp / f"test-{cap}.rs"
        binary = tmp / f"test-{cap}"
        test.write_text(src.replace(marker, f"const POOL_CAP: usize = {cap};") + "\n" + tail)
        subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C",
                        "overflow-checks=yes", "-C", "debug-assertions=yes",
                        str(test), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
print("PASS 15,000 mixed queries across six capacities")

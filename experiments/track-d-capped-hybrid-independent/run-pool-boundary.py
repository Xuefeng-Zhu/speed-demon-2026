#!/usr/bin/env python3
"""Exercise the exact default-capacity source without editing it."""
from pathlib import Path
import hashlib
import subprocess
import tempfile

here = Path(__file__).resolve().parent
source = here.parent / "track-d-capped-hybrid" / "candidate.rs"
expected = "671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c"
text = source.read_text()
assert hashlib.sha256(text.encode()).hexdigest() == expected
with tempfile.TemporaryDirectory(prefix="sd-pool-boundary-") as temp:
    tmp = Path(temp)
    test = tmp / "pool.rs"
    binary = tmp / "pool-test"
    test.write_text(text + "\n" + (here / "pool-boundary-tail.rs").read_text())
    subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C", "overflow-checks=yes", "-C", "debug-assertions=yes", str(test), "-o", str(binary)], check=True)
    subprocess.run([str(binary), "--nocapture"], check=True)

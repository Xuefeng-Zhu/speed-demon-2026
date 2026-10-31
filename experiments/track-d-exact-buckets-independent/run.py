#!/usr/bin/env python3
"""Compare both CSR multisets and assert no scatter bucket reallocates."""
from pathlib import Path
import hashlib
import subprocess
import tempfile

here = Path(__file__).resolve().parent
src = (here.parent / "track-d-exact-buckets" / "candidate.rs").read_text()
assert hashlib.sha256(src.encode()).hexdigest() == "e4caa9848aadb4af327ef99cd00a2e8a0454c6ce28ea226c2485a84d44330e0e"
old = """                        out[0][block(u)].push((u, v, w));
                        out[1][block(v)].push((v, u, w));"""
new = """                        let (a, b) = (block(u), block(v));
                        assert!(out[0][a].len() < out[0][a].capacity());
                        assert!(out[1][b].len() < out[1][b].capacity());
                        out[0][a].push((u, v, w));
                        out[1][b].push((v, u, w));"""
assert src.count(old) == 1
with tempfile.TemporaryDirectory(prefix="sd-exact-loader-review-") as tmp:
    tmp = Path(tmp)
    test = tmp / "loader.rs"
    binary = tmp / "loader-test"
    test.write_text(src.replace(old, new) + "\n" + (here / "loader-tail.rs").read_text())
    subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C",
                    "overflow-checks=yes", "-C", "debug-assertions=yes",
                    str(test), "-o", str(binary)], check=True)
    subprocess.run([str(binary), "--nocapture"], check=True)

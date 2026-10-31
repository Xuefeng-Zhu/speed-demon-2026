#!/usr/bin/env python3
"""Compile an unmodified copy of the candidate with the independent test module."""
import hashlib
import pathlib
import subprocess
import tempfile

here = pathlib.Path(__file__).resolve().parent
candidate = here.parent / "c-fused-owner-rebase" / "rowcache.rs"
expected = "76b341e2b7e880fe4ceeee220206a63b48cd247bba4448aa7991a7ad825e8dd2"
data = candidate.read_bytes()
assert hashlib.sha256(data).hexdigest() == expected
with tempfile.TemporaryDirectory(prefix="c-rowcache-independent-") as temp:
    temp = pathlib.Path(temp)
    source = temp / "test.rs"
    source.write_bytes(data + b"\n" + (here / "test-tail.rs").read_bytes())
    binary = temp / "test"
    subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C", "overflow-checks=yes", "-C", "debug-assertions=yes", str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary), "--nocapture"], check=True)

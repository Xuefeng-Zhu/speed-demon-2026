#!/usr/bin/env python3
"""Compile the exact candidate plus independent fake-writer tests, then run them."""
import pathlib
import subprocess
import tempfile

here = pathlib.Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="sd-a-writev-tests-") as d:
    root = pathlib.Path(d)
    source = root / "tests.rs"
    source.write_text((here / "candidate.rs").read_text() + "\n" + (here / "test-tail.rs").read_text())
    exe = root / "tests"
    subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C", "overflow-checks=yes",
                    "-C", "debug-assertions=yes", str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

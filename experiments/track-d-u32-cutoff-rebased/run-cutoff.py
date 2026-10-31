#!/usr/bin/env python3
"""Exercise exact cutoff decisions and narrow/wide state reuse."""
from pathlib import Path
import subprocess
import tempfile

here = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="sd-u32-cutoff-") as tmp:
    tmp = Path(tmp)
    source = tmp / "candidate-tests.rs"
    source.write_text((here / "candidate.rs").read_text() + "\n" +
                      (here / "cutoff-tail.rs").read_text())
    binary = tmp / "cutoff-tests"
    subprocess.run(["rustc", "--edition=2021", "--test", "-O",
                    "-C", "overflow-checks=yes", "-C", "debug-assertions=yes",
                    str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary), "--nocapture"], check=True)

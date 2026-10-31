#!/usr/bin/env python3
"""Pin the reviewed candidate and run independent simulated-path properties."""
import hashlib
import pathlib
import subprocess
import tempfile

here = pathlib.Path(__file__).resolve().parent
candidate = here.parent / "a-crc-bounded15" / "candidate.rs"
source = candidate.read_bytes()
assert hashlib.sha256(source).hexdigest() == "9028986cf2546dfc008cf05dfdb32648cf64b6536223b933fe820cd69deb89e9"
with tempfile.TemporaryDirectory(prefix="a-crc-independent-") as tmp:
    tmp = pathlib.Path(tmp)
    source_path = tmp / "candidate.rs"
    source_path.write_bytes(source + b"\n" + (here / "tail.rs").read_bytes())
    binary = tmp / "test"
    subprocess.run(["rustc", "--edition=2021", "--test", "-O", "--cfg", "sd_crc_sim", str(source_path), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

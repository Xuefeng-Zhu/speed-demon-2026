#!/usr/bin/env python3
"""Prepare exact-source forced-hash integration binaries; never change a candidate.

Run inside the pinned native Linux x86 tool image:
    python3 experiments/a-shared-dictionary/prepare-forced.py --build

Then use the existing check.py and adversarial.py with the printed binary paths.
Each test copy differs in exactly one parser statement: all endpoint hashes are 0.
This is correctness stress only; its timings are not candidate performance.
"""

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="compile the test copies natively")
    parser.add_argument("--source", action="append", help="source filename in this directory; repeatable")
    args = parser.parse_args()
    if args.build:
        if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
            raise SystemExit("--build requires native Linux x86-64 with x86-64-v3 features")
        if "avx2" not in Path("/proc/cpuinfo").read_text().lower().split():
            raise SystemExit("CPU must report AVX2")
    here = Path(__file__).resolve().parent
    target = here / "target"
    target.mkdir(parents=True, exist_ok=True)
    flags = ["--edition=2021", "-C", "opt-level=3", "-C", "lto=fat", "-C",
             "codegen-units=1", "-C", "panic=abort", "-C", "target-cpu=x86-64-v3",
             "--crate-name", "solution"]
    needle = "        let h = hash(d, s, e - s);"
    replacement = "        let h = 0u64; // TEST ONLY: force every endpoint hash to collide."
    records = []
    for filename in args.source or ["shared-box.rs", "shared-inline.rs"]:
        if Path(filename).name != filename or not filename.endswith(".rs"):
            raise SystemExit("--source must be a .rs filename in this directory")
        original = here / filename
        source = original.read_text()
        if source.count(needle) != 1:
            raise SystemExit(f"{filename}: expected exactly one endpoint-hash statement")
        forced = source.replace(needle, replacement, 1)
        assert forced.replace(replacement, needle, 1) == source
        stem = original.stem + "-forced-hash"
        output, binary = target / (stem + ".rs"), target / stem
        output.write_text(forced)
        record = {
            "candidate": filename,
            "source_sha256": digest(source.encode()),
            "forced_source": str(output),
            "forced_source_sha256": digest(forced.encode()),
            "test_change": "parser endpoint hash forced to 0; all other source is identical",
            "rustc_flags": flags,
            "binary": None,
        }
        if args.build:
            subprocess.run(["rustc", *flags, str(output), "-o", str(binary)], check=True)
            record["binary"] = str(binary)
            record["binary_sha256"] = digest(binary.read_bytes())
        records.append(record)
        print(json.dumps(record), flush=True)
    (target / "forced-hash-manifest.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()

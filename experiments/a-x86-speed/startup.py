#!/usr/bin/env python3
"""Startup and exit cost of Track A binaries on an empty requests.log (local diagnostic, stdlib).

Builds every --variant NAME=PATH.rs[=RUSTC ARGS] with the production rustc flags (like bench.py),
then runs each binary and /bin/true (process spawn floor of this Python driver) --runs times in
shuffled order with SD_THREADS=8 on an empty input under .data/a-empty, and reports wall-time
medians in ms, the binaries' `ldd` output and every sample. Local x86 VM numbers only.
"""
import argparse
import json
import os
import random
import shlex
import statistics
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FLAGS = ["--edition", "2021", "-C", "opt-level=3", "-C", "codegen-units=1", "-C", "lto=fat",
         "-C", "panic=abort", "-C", "target-cpu=x86-64-v3"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--variant", action="append", required=True)
    p.add_argument("--runs", type=int, default=300)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--report")
    a = p.parse_args()
    data, out = REPO / ".data/a-empty", REPO / ".out/a-empty"
    data.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    (data / "requests.log").write_bytes(b"")
    (HERE / "target").mkdir(exist_ok=True)
    bins, info = {"true": "/bin/true"}, {}
    for v in a.variant:
        name, _, rest = v.partition("=")
        src, _, extra = rest.partition("=")
        binary = HERE / "target" / f"startup-{name}"
        r = subprocess.run(["rustc", *FLAGS, *shlex.split(extra), "-o", str(binary), src],
                           capture_output=True, text=True)
        info[name] = {"source": src, "extra_rustc_args": shlex.split(extra),
                      "built": r.returncode == 0, "build_error_tail": r.stderr[-600:]}
        if r.returncode == 0:
            bins[name] = str(binary)
            info[name]["ldd"] = subprocess.run(["ldd", str(binary)], capture_output=True,
                                               text=True).stdout
    env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out), SD_THREADS="8")
    rng, names = random.Random(a.seed), list(bins)
    samples = {n: [] for n in names}
    for _ in range(a.runs):
        rng.shuffle(names)
        for n in names:
            t = time.perf_counter()
            subprocess.run([bins[n]], env=env, check=True)
            samples[n].append((time.perf_counter() - t) * 1e3)
    report = {"note": "Local x86 VM wall times in ms on an empty input, including the Python "
                      "driver's spawn cost (see /bin/true); not official scores.",
              "runs": a.runs, "seed": a.seed, "variants": info, "median_ms": {}, "samples_ms": samples}
    for n in bins:
        report["median_ms"][n] = statistics.median(samples[n])
        print(f"{n:>10} {report['median_ms'][n]:7.3f} ms")
    for n, i in info.items():
        if not i["built"]:
            print(f"{n:>10} did not build:\n{i['build_error_tail']}")
    if a.report:
        Path(a.report).write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()

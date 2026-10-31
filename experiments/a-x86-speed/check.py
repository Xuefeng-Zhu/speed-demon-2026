#!/usr/bin/env python3
"""Track A correctness suite for one binary (local helper, python3 stdlib only).

Runs, from the repo root:
  1. the full seed-1 input at SD_THREADS 1,2,3,6,8,12 and unset; every summary.txt must hash to
     the published full seed-1 SHA-256,
  2. track-a-verification/test.py (--io directories), page_end_test.py (vs the official
     reference) and latency_grid_test.py,
  3. sample seeds 2, 98, 999, 4242 compared byte for byte with the official reference output.
Missing inputs and reference outputs are generated under the gitignored .data/ directory.
Exits non-zero on any failure.
"""
import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EXPECTED = "495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3"
GEN = REPO / "official/generators/a_ingest.py"
REF = REPO / "official/reference/a_ingest.py"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run_binary(binary, data, out, threads=None):
    out.mkdir(parents=True, exist_ok=True)
    summary = out / "summary.txt"
    summary.unlink(missing_ok=True)
    env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out))
    env.pop("SD_THREADS", None)
    if threads is not None:
        env["SD_THREADS"] = str(threads)
    subprocess.run([str(binary)], env=env, check=True)
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("binary")
    ap.add_argument("--data", default=str(REPO / ".data/a-full"))
    ap.add_argument("--threads", default="1,2,3,6,8,12,default")
    ap.add_argument("--seeds", default="2,98,999,4242")
    args = ap.parse_args()
    binary = Path(args.binary).resolve()
    data = Path(args.data)
    out = REPO / ".out/check"
    failures = []

    def report(ok, what):
        print(f"{'ok  ' if ok else 'FAIL'} {what}", flush=True)
        if not ok:
            failures.append(what)

    if not (data / "requests.log").exists():
        subprocess.run([sys.executable, str(GEN), "--seed", "1", "--scale", "full", "--out",
                        str(data)], check=True)
    for t in args.threads.split(","):
        threads = None if t == "default" else int(t)
        digest = sha256(run_binary(binary, data, out, threads))
        report(digest == EXPECTED, f"full seed-1 SD_THREADS={t} sha256={digest}")

    scripts = [
        ["test.py", "--binary", str(binary), "--io", "directories"],
        ["page_end_test.py", "--binary", str(binary), "--reference", str(REF)],
        ["latency_grid_test.py", "--binary", str(binary)],
    ]
    for argv in scripts:
        r = subprocess.run([sys.executable, str(REPO / "track-a-verification" / argv[0]), *argv[1:]],
                           cwd=REPO, capture_output=True, text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        report(r.returncode == 0, f"{argv[0]} exit={r.returncode} {tail[0]}")

    for seed in args.seeds.split(","):
        sdata = REPO / f".data/a-sample-{seed}"
        sref = REPO / f".data/ref-{seed}"
        if not (sdata / "requests.log").exists():
            subprocess.run([sys.executable, str(GEN), "--seed", seed, "--scale", "sample", "--out",
                            str(sdata)], check=True)
        if not (sref / "summary.txt").exists():
            subprocess.run([sys.executable, str(REF), "--data", str(sdata), "--out", str(sref)],
                           check=True)
        mine = run_binary(binary, sdata, out)
        same = mine.read_bytes() == (sref / "summary.txt").read_bytes()
        report(same, f"sample seed {seed} matches official reference")

    print(f"{len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""pairs.py --data DIR [--threads N] [--rounds 31] [--json OUT] BASE CAND

Paired wall-time comparison: one warm-up run each, then `rounds` rounds that run both binaries
in random order. Prints the median wall of each and the median of the per-round ratios
CAND/BASE, with the number of rounds CAND was faster. Outputs go to --out (keep it on a disk
file system, so O_DIRECT is taken) and must be byte-identical between the two in every round.
Local sandbox timings only, not board results.
"""
import argparse, hashlib, json, os, random, shutil, statistics, subprocess, time

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--data", required=True)
ap.add_argument("--out", default="/projects/sandbox/.out/pairs")
ap.add_argument("--threads")
ap.add_argument("--rounds", type=int, default=31)
ap.add_argument("--json")
ap.add_argument("base")
ap.add_argument("cand")
a = ap.parse_args()


def run(binary):
    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(a.out)
    env = dict(os.environ, SD_DATA=a.data, SD_OUT=a.out)
    if a.threads:
        env["SD_THREADS"] = a.threads
    t = time.perf_counter()
    subprocess.run([binary], env=env, check=True)
    wall = time.perf_counter() - t
    return wall, hashlib.sha256(open(os.path.join(a.out, "summary.txt"), "rb").read()).hexdigest()


run(a.base), run(a.cand)
rounds = []
for _ in range(a.rounds):
    res = {b: run(b) for b in random.sample([a.base, a.cand], 2)}
    assert res[a.base][1] == res[a.cand][1], "outputs differ"
    rounds.append((res[a.base][0], res[a.cand][0]))
ratio = statistics.median(c / b for b, c in rounds)
wins = sum(c < b for b, c in rounds)
print(f"base {statistics.median(b for b, _ in rounds) * 1e3:.1f} ms  "
      f"cand {statistics.median(c for _, c in rounds) * 1e3:.1f} ms  "
      f"paired cand/base {ratio:.4f}  cand faster {wins}/{a.rounds}")
if a.json:
    json.dump(dict(threads=a.threads, base=a.base, cand=a.cand, rounds=rounds), open(a.json, "w"), indent=1)

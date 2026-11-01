#!/usr/bin/env python3
"""CPU attribution of Track A from cpu.rs mode builds (local diagnostic, outputs not checked).

Runs each prebuilt mode binary in target/ on the full seed-1 input at SD_THREADS (default 1, so
there is no lock or page-fault contention between threads), in shuffled rounds, and prints the
median thread-CPU milliseconds of each phase that the binary reports on stderr. Usage:
attribute.py [ROUNDS] [THREADS]. Writes attribute-<THREADS>.json.
"""
import json, os, random, re, statistics, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MODES = ["full", "lines", "fields", "scan", "notable", "nopush", "nosel", "nosmall", "nobig", "nofmt",
         "full-pop", "lines-pop", "fields-pop", "notable-pop", "nopush-pop"]
rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 11
threads = sys.argv[2] if len(sys.argv) > 2 else "1"
out = REPO / ".out/cpuprof"
out.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, SD_DATA=str(REPO / ".data/a-full"), SD_OUT=str(out), SD_THREADS=threads)
samples = {m: [] for m in MODES}
rng = random.Random(5)
for r in range(rounds + 1):
    order = MODES[:]
    rng.shuffle(order)
    for m in order:
        (out / "summary.txt").unlink(missing_ok=True)
        err = subprocess.run([str(HERE / "target" / m)], env=env, stderr=subprocess.PIPE, text=True, check=True).stderr
        if r:
            samples[m].append({k: float(v) for k, v in re.findall(r"(\w+)=([\d.]+)", err.split("cpu ")[-1])})
med = {m: {k: statistics.median(s[k] for s in samples[m]) for k in samples[m][0]} for m in MODES}
for m in MODES:
    q = sorted(x["parse"] for x in samples[m])
    iqr = q[3 * len(q) // 4] - q[len(q) // 4]
    print(f"{m:>12} " + " ".join(f"{k}={v:7.2f}" for k, v in med[m].items()) + f"  parse IQR {iqr:5.2f}")
(HERE / f"attribute-{threads}.json").write_text(json.dumps({"median": med, "samples": samples}, indent=1))

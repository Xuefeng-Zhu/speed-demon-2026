#!/usr/bin/env python3
"""Paired interleaved Track A benchmark (local x86 measurements only, not official scoring).

Builds every --variant NAME=PATH.rs with identical production-equivalent rustc flags into the
gitignored experiments/a-x86-speed/target/, then for each thread count runs warmup rounds
(discarded) and measured rounds. Every round runs every variant once in a freshly shuffled order
(seeded RNG, seed recorded). The previous summary.txt is removed before each run, wall time is
time.perf_counter around the child, utime/stime/maxrss come from os.wait4, and every output
SHA-256 is checked against --expected. The first variant is the baseline: the report holds raw
samples, median, min, mean of the middle 60%, a board-style statistic (mean of the middle 3 of
each consecutive block of 5 runs, averaged over blocks), and per-round paired ratios
candidate/baseline with their median and the fraction of rounds the candidate was faster.
"""
import argparse
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EXPECTED = "495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3"
RUSTFLAGS = ["--edition", "2021", "-C", "opt-level=3", "-C", "codegen-units=1", "-C", "lto=fat",
             "-C", "panic=abort", "-C", "target-cpu=x86-64-v3"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cmd_out(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        return f"unavailable: {e}"


def run_once(binary, data, out, threads, expected):
    summary = out / "summary.txt"
    summary.unlink(missing_ok=True)
    env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out))
    env.pop("SD_THREADS", None)
    if threads != "default":
        env["SD_THREADS"] = str(threads)
    t0 = time.perf_counter()
    proc = subprocess.Popen([str(binary)], env=env, stdout=subprocess.DEVNULL)
    _, status, ru = os.wait4(proc.pid, 0)
    wall = time.perf_counter() - t0
    code = os.waitstatus_to_exitcode(status)
    if code != 0:
        raise SystemExit(f"{binary} threads={threads} exited {code}")
    digest = sha256(summary)
    if digest != expected:
        raise SystemExit(f"hash mismatch {binary} threads={threads}: {digest}")
    return {"wall": wall, "utime": ru.ru_utime, "stime": ru.ru_stime,
            "maxrss_kib": ru.ru_maxrss, "sha256": digest}


def middle_mean(xs, frac=0.6):
    s = sorted(xs)
    drop = int(round(len(s) * (1 - frac) / 2))
    mid = s[drop:len(s) - drop] or s
    return statistics.fmean(mid)


def board_style(xs):
    """Mean over consecutive blocks of 5 runs of the mean of each block's middle 3."""
    blocks = [sorted(xs[i:i + 5])[1:4] for i in range(0, len(xs) - len(xs) % 5, 5)]
    return statistics.fmean(statistics.fmean(b) for b in blocks) if blocks else None


def describe(xs):
    return {"n": len(xs), "median": statistics.median(xs), "min": min(xs), "max": max(xs),
            "mean": statistics.fmean(xs), "middle60_mean": middle_mean(xs),
            "board_style": board_style(xs)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--variant", action="append", required=True, metavar="NAME=PATH.rs",
                    help="repeatable; the first one is the baseline")
    ap.add_argument("--data", default=str(REPO / ".data/a-full"))
    ap.add_argument("--out", default=str(REPO / ".out/bench"))
    ap.add_argument("--threads", default="8,12", help="comma list; 'default' leaves SD_THREADS unset")
    ap.add_argument("--runs", type=int, default=21, help="measured rounds per thread count")
    ap.add_argument("--warmup", type=int, default=2, help="discarded rounds per thread count")
    ap.add_argument("--seed", type=int, default=None, help="shuffle RNG seed (random if unset)")
    ap.add_argument("--report", default=None)
    ap.add_argument("--expected", default=EXPECTED)
    args = ap.parse_args()

    variants = []
    for v in args.variant:
        name, sep, path = v.partition("=")
        if not sep or not name or not path:
            raise SystemExit(f"bad --variant {v!r}, want NAME=PATH.rs")
        if name in (n for n, _ in variants):
            raise SystemExit(f"duplicate variant name {name}")
        variants.append((name, Path(path).resolve()))
    names = [n for n, _ in variants]
    base = names[0]
    threads_list = [t if t == "default" else int(t) for t in args.threads.split(",")]
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1 << 32)
    rng = random.Random(seed)
    data, out = Path(args.data), Path(args.out)
    if not (data / "requests.log").exists():
        raise SystemExit(f"missing {data}/requests.log (see experiments/a-x86-speed/README.md)")
    out.mkdir(parents=True, exist_ok=True)

    build = HERE / "target"
    build.mkdir(exist_ok=True)
    bins, sources = {}, {}
    for name, src in variants:
        bins[name] = build / f"bench-{name}"
        sources[name] = {"path": os.path.relpath(src, REPO), "sha256": sha256(src)}
        subprocess.run(["rustc", *RUSTFLAGS, "-o", str(bins[name]), str(src)], check=True)
        sources[name]["binary_sha256"] = sha256(bins[name])

    report = {
        "note": "Local x86 VM measurements on a shared, noisy host; not official scores.",
        "host": {
            "cpu_model": next((l.split(":", 1)[1].strip() for l in cmd_out(["lscpu"]).splitlines()
                               if l.startswith("Model name")), "unknown"),
            "nproc": os.cpu_count(), "kernel": platform.release(), "rustc": cmd_out(["rustc", "-V"]),
            "python": platform.python_version(),
        },
        "input": {"path": os.path.relpath(data / "requests.log", REPO),
                  "bytes": (data / "requests.log").stat().st_size},
        "expected_output_sha256": args.expected,
        "rustc_flags": RUSTFLAGS,
        "sources": sources,
        "config": {"threads": threads_list, "runs": args.runs, "warmup": args.warmup,
                   "shuffle_seed": seed, "baseline": base},
        "rounds": [], "summary": {},
    }

    for t in threads_list:
        for r in range(-args.warmup, args.runs):
            order = names[:]
            rng.shuffle(order)
            row = {"threads": t, "round": r, "warmup": r < 0, "order": order, "runs": {}}
            for name in order:
                row["runs"][name] = run_once(bins[name], data, out, t, args.expected)
            report["rounds"].append(row)
        print(f"threads {t}: done", file=sys.stderr, flush=True)

    lines = [f"{'threads':>7} {'variant':>12} {'median':>8} {'mid60':>8} {'board':>8} {'min':>8}"
             f" {'ratio_med':>9} {'win%':>5}"]
    for t in threads_list:
        rows = [r for r in report["rounds"] if r["threads"] == t and not r["warmup"]]
        per = {}
        for name in names:
            walls = [r["runs"][name]["wall"] for r in rows]
            entry = {"wall": describe(walls), "wall_samples": walls,
                     "utime_median": statistics.median(r["runs"][name]["utime"] for r in rows),
                     "stime_median": statistics.median(r["runs"][name]["stime"] for r in rows),
                     "maxrss_kib_median": statistics.median(r["runs"][name]["maxrss_kib"]
                                                            for r in rows)}
            if name != base:
                ratios = [r["runs"][name]["wall"] / r["runs"][base]["wall"] for r in rows]
                entry["paired_ratio"] = {**describe(ratios), "samples": ratios,
                                         "win_fraction": sum(x < 1 for x in ratios) / len(ratios)}
            per[name] = entry
            pr = entry.get("paired_ratio")
            lines.append(f"{t!s:>7} {name:>12} {entry['wall']['median']:8.4f} "
                         f"{entry['wall']['middle60_mean']:8.4f} "
                         f"{(entry['wall']['board_style'] or 0):8.4f} {entry['wall']['min']:8.4f} "
                         + (f"{pr['median']:9.4f} {100 * pr['win_fraction']:5.0f}" if pr else
                            f"{'base':>9} {'':>5}"))
        report["summary"][str(t)] = per

    report["all_hashes_ok"] = all(x["sha256"] == args.expected for r in report["rounds"]
                                  for x in r["runs"].values())
    print("\n".join(lines))
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1) + "\n")
        print(f"wrote {args.report}; all hashes ok: {report['all_hashes_ok']}", file=sys.stderr)
    sys.exit(0 if report["all_hashes_ok"] else 1)


if __name__ == "__main__":
    main()

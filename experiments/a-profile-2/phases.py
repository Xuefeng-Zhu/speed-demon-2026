#!/usr/bin/env python3
"""Phase timings of the instrumented Track A build (target/timed from timed.rs), local only.

Runs the binary on the full seed-1 input at each thread count, 2 warmups then N measured runs,
checks every output hash, and prints medians of: process wall (driver), user and sys time
(wait4), the first, median and last parse-thread finish, the barrier release, plan done, the
first and last summary-worker finish, the last write and the end of main, plus the sums of
per-thread CPU in the parse and summary phases. Writes all samples to phases.json.
"""
import hashlib, json, os, re, statistics, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EXPECTED = "495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3"
runs = int(sys.argv[1]) if len(sys.argv) > 1 else 21
out = REPO / ".out/prof2"
out.mkdir(parents=True, exist_ok=True)
report = {}
for th in (sys.argv[2] if len(sys.argv) > 2 else "8,12,20").split(","):
    env = dict(os.environ, SD_DATA=str(REPO / ".data/a-full"), SD_OUT=str(out), SD_THREADS=th)
    rows = []
    for r in range(runs + 2):
        t0 = time.perf_counter()
        p = subprocess.Popen([str(HERE / "target/timed")], env=env, stderr=subprocess.PIPE, text=True)
        err = p.stderr.read()
        _, status, ru = os.wait4(p.pid, 0)
        wall = (time.perf_counter() - t0) * 1e3
        assert status == 0
        h = hashlib.sha256((out / "summary.txt").read_bytes()).hexdigest()
        assert h == EXPECTED, h
        if r < 2:
            continue
        pe = sorted(float(x) for x in re.findall(r"parse_end t=\d+ ([\d.]+)", err))
        pc = [float(x) for x in re.findall(r"parse_end t=\d+ [\d.]+ cpu=([\d.]+)", err)]
        we = sorted(float(x) for x in re.findall(r"work_end t=\d+ ([\d.]+)", err))
        wc = [float(x) for x in re.findall(r"work_end t=\d+ [\d.]+ cpu=([\d.]+)", err)]
        v = {k: float(x) for k, x in re.findall(r"^(barrier|plan|written|done) ([\d.]+)", err, re.M)}
        rows.append(dict(wall=wall, user=ru.ru_utime * 1e3, sys=ru.ru_stime * 1e3,
                         parse_first=pe[0], parse_med=pe[len(pe) // 2], parse_last=pe[-1],
                         barrier=v["barrier"], plan=v["plan"], work_first=we[0], work_last=we[-1],
                         written=v["written"], done=v["done"], parse_cpu=sum(pc),
                         parse_cpu_max=max(pc), summary_cpu=sum(wc), minflt=ru.ru_minflt))
    med = {k: statistics.median(r[k] for r in rows) for k in rows[0]}
    report[th] = {"median": med, "runs": rows}
    print(f"threads {th}: " + " ".join(f"{k}={v:.2f}" for k, v in med.items()), flush=True)
(HERE / "phases.json").write_text(json.dumps(report, indent=1))

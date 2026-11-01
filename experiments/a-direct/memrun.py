#!/usr/bin/env python3
"""memrun.py --data DIR [--expect SHA256] [--threads N] [--runs 21] [--json OUT] NAME=BIN ...

Runs the binaries interleaved (one warm-up run each, then `runs` rounds in random order) and
reports, per binary, median wall time, the sampled peak of RssAnon + RssShmem + VmPTE ("anon")
and an estimate of the board's cgroup peak ("est M"): the sampled peak of anon plus the output
bytes in the page cache at that moment. Output residency is taken from `fincore` on the finished
file before anything reads it: a buffered write leaves the whole file resident, an O_DIRECT write
none of it, so est M adds the output size written so far times that resident fraction. With
--expect (for the full seed-1 log, the published 495ca096...1cd3) every output must match it.

Local estimates only: this sandbox has no cgroup memory controller, the sampler polls every
0.2 ms and can miss short peaks, and the board adds memory this does not see.
"""
import argparse, hashlib, json, os, random, shutil, statistics, subprocess, threading, time

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--data", required=True)
ap.add_argument("--out", default="/projects/sandbox/.out/memrun", help="on a disk file system")
ap.add_argument("--expect")
ap.add_argument("--threads")
ap.add_argument("--runs", type=int, default=21)
ap.add_argument("--json")
ap.add_argument("bins", nargs="+")
a = ap.parse_args()
bins = dict(b.split("=", 1) for b in a.bins)


def kb(status, key):
    line = next((l for l in status.splitlines() if l.startswith(key + ":")), None)
    return int(line.split()[1]) if line else 0


def run(binary):
    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(a.out)
    out = os.path.join(a.out, "summary.txt")
    env = dict(os.environ, SD_DATA=a.data, SD_OUT=a.out)
    if a.threads:
        env["SD_THREADS"] = a.threads
    samples = []
    t0 = time.perf_counter()
    p = subprocess.Popen([binary], env=env)

    def sample():
        while p.poll() is None:
            try:
                st = open(f"/proc/{p.pid}/status").read()
                size = os.path.getsize(out) if os.path.exists(out) else 0
            except OSError:
                break
            anon = (kb(st, "RssAnon") + kb(st, "RssShmem") + kb(st, "VmPTE")) * 1024
            samples.append((anon, size))
            time.sleep(0.0002)

    th = threading.Thread(target=sample)
    th.start()
    p.wait()
    wall = time.perf_counter() - t0
    th.join()
    size = os.path.getsize(out)
    res = subprocess.run(["fincore", "--bytes", "--noheadings", "--raw", "-o", "RES", out],
                         capture_output=True, text=True, check=True).stdout.strip()
    resident = int(res) / size if size else 0.0
    digest = hashlib.sha256(open(out, "rb").read()).hexdigest()
    anon = max((s[0] for s in samples), default=0)
    est = max((s[0] + resident * s[1] for s in samples), default=0)
    return dict(wall=wall, anon=anon, est=est, resident=resident, sha=digest)


for b in bins.values():
    run(b)
rows = {n: [] for n in bins}
for _ in range(a.runs):
    for n in random.sample(list(bins), len(bins)):
        r = run(bins[n])
        assert a.expect in (None, r["sha"]), f"{n}: wrong output {r['sha']}"
        rows[n].append(r)
for n, rs in rows.items():
    med = lambda k: statistics.median(r[k] for r in rs)
    print(f"{n:14s} wall {med('wall') * 1e3:6.1f} ms  anon {med('anon') / 1e6:6.2f} MB  "
          f"est M {med('est') / 1e6:6.2f} MB  output resident {med('resident'):.0%}")
if a.json:
    json.dump(dict(threads=a.threads, runs=a.runs, bins=bins, rows=rows), open(a.json, "w"), indent=1)

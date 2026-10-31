#!/usr/bin/env python3
"""Adversarial Track A inputs for the endpoint scan, table and record escapes (stdlib only).

Byte-compares the binary's summary.txt with the official reference on inputs that stress the
parse paths changed on branch a-x86-speed:

- lengths: every endpoint length 1..125 (plus 126..300, beyond the spec, for the slow scan and
  long compare paths), under every method so endpoints start at many offsets, and families that
  share first, middle and last words but differ elsewhere (equal hashes from the cheap words);
- distinct: 5,000 and 70,000 distinct endpoints, so local tables grow and shared ids pass 2047
  (escaped records);
- latency: boundary latencies 0, 2^20 - 2 .. 2^20, 2^32 - 1, many digits;
- group-sizes: in two hours, groups of every size 1..200 (the summary's small-group rank paths
  and the selection path) whose latencies are heavily tied, all equal, around 2^31 and 2^32 - 1,
  or spread over 32 bits, in shuffled line order.

Usage: adversarial.py --binary BIN [--quick] (--quick skips the 70,000-endpoint case, for a
binary built with a forced constant hash where every probe collides).
"""
import argparse
import datetime
import os
import pathlib
import random
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REF = HERE.parent.parent / "official" / "reference" / "a_ingest.py"
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/-_.{}:"
METHODS = ["GET", "PUT", "POST", "HEAD", "PATCH", "DELETE", "OPTIONS"]
LATENCIES = [0, 1, 9, 10, 99999999, 100000000, 1048574, 1048575, 1048576, 4294967295, 4294967294]
BASE = datetime.datetime(2026, 10, 30, 18)


def endpoint(rng, n):
    return "/" + "".join(rng.choice(CHARS) for _ in range(n - 1))


def families(rng):
    """Endpoints of one length sharing first 8, middle 8 and last 8 bytes, differing elsewhere."""
    out = []
    for n in (24, 40, 63, 64, 65, 100, 125):
        core = list(endpoint(rng, n))
        mid = n // 2 - 4
        keep = set(range(8)) | set(range(mid, mid + 8)) | set(range(n - 8, n))
        free = [k for k in range(1, n) if k not in keep]
        for v in range(40):
            e = core[:]
            for k in rng.sample(free, min(3, len(free))):
                e[k] = CHARS[(CHARS.index(e[k]) + 1 + v) % len(CHARS)]
            out.append("".join(e))
    return out


def lines(rng, endpoints, count):
    out = []
    for i in range(count):
        ep = endpoints[i % len(endpoints)] if i < len(endpoints) else rng.choice(endpoints)
        when = BASE + datetime.timedelta(hours=rng.randrange(72), seconds=rng.randrange(3600),
                                         microseconds=rng.randrange(1000000))
        lat = rng.choice(LATENCIES) if rng.random() < 0.3 else rng.randrange(1 << rng.randrange(1, 33))
        status = rng.choice([100, 200, 404, 499, 500, 503, 599])
        out.append(f"{when.strftime('%Y-%m-%dT%H:%M:%S.%fZ')} {rng.choice(METHODS)} {ep} {status} {lat}\n")
    return out


def group_sizes(rng):
    out = []
    edges = [0, 1, 2**31 - 1, 2**31, 2**31 + 1, 2**32 - 2, 2**32 - 1]
    patterns = {
        "tied": lambda: rng.randrange(3),
        "equal": None,
        "edges": lambda: rng.choice(edges),
        "wide": lambda: rng.randrange(1 << 32),
    }
    for hour in (0, 71):
        for name, draw in patterns.items():
            for n in range(1, 201):
                same = rng.randrange(1 << 32)
                for _ in range(n):
                    when = BASE + datetime.timedelta(hours=hour, seconds=rng.randrange(3600))
                    lat = same if draw is None else draw()
                    status = rng.choice([200, 404, 500, 503])
                    out.append(f"{when.strftime('%Y-%m-%dT%H:%M:%S.%fZ')} GET /g/{name}/{n} "
                               f"{status} {lat}\n")
    rng.shuffle(out)
    return out


def cases(rng, quick):
    lengths = [endpoint(rng, n) for n in range(1, 301)] + ["/"] + families(rng)
    yield "lengths", lines(rng, lengths, 60000)
    yield "distinct-5000", lines(rng, [f"/d/{k}" for k in range(5000)], 40000)
    if not quick:
        many = [endpoint(rng, rng.randrange(2, 126)) for _ in range(70000)]
        yield "distinct-70000", lines(rng, many, 150000)
    yield "latency", lines(rng, ["/", "/a", "/v2/orders", "/v2/orders/{id}"], 30000)
    yield "group-sizes", group_sizes(rng)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--binary", required=True)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--threads", default="1,2,3,7,12")
    a = p.parse_args()
    binary = str(pathlib.Path(a.binary).resolve())
    rng = random.Random(20261031)
    failures = 0
    with tempfile.TemporaryDirectory(prefix="a-adv-") as td:
        root = pathlib.Path(td)
        data, actual, expected = root / "data", root / "actual", root / "expected"
        for d in (data, actual, expected):
            d.mkdir()
        for name, text in cases(rng, a.quick):
            (data / "requests.log").write_text("".join(text), encoding="ascii")
            subprocess.run(["python3", str(REF), "--data", str(data), "--out", str(expected)],
                           check=True, stdout=subprocess.DEVNULL)
            want = (expected / "summary.txt").read_bytes()
            for t in a.threads.split(","):
                env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(actual), SD_THREADS=t)
                subprocess.run([binary], env=env, check=True)
                ok = (actual / "summary.txt").read_bytes() == want
                failures += not ok
                print(f"{'ok  ' if ok else 'FAIL'} {name} lines={len(text)} threads={t}", flush=True)
    print(f"{failures} failure(s)")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

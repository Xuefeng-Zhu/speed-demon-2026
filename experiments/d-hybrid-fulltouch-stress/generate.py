#!/usr/bin/env python3
"""Generate synthetic D memory-stress fixtures, run binaries, and clean up.

The default dimensions match the official full scale, but neither graph
shape nor the repeated query set follows the official generator distribution.
Pass smaller dimensions to exercise the script quickly. No files survive the
temporary directory's cleanup, including on an exception or timeout.
"""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


MAX_WEIGHT = 2**32 - 1


def generate(data: Path, shape: str, n: int, m: int, q: int, heavy: int) -> bytes:
    """Write exactly m directed edges and q queries; return exact output bytes."""
    if n < 3 or n > 2**32 - 3:
        raise ValueError("n must be between 3 and 2^32-3")
    if q < 0 or heavy < 0:
        raise ValueError("q and heavy must be nonnegative")
    minimum = n - 1 if shape == "chain" else 2 * (n - 2)
    if m < minimum:
        raise ValueError(f"{shape} needs at least {minimum} edges")
    if m > 2**32 - 1:
        raise ValueError("m must fit the candidate's u32 CSR offsets")
    data.mkdir()
    with (data / "graph.txt").open("w", encoding="ascii", buffering=1024 * 1024) as f:
        f.write(f"{n} {m}\n")
        if shape == "chain":
            middle = (n - 2) // 2
            for u in range(n - 1):
                weight = MAX_WEIGHT if u == middle else 1
                f.write(f"{u} {u + 1} {weight}\n")
            distance = MAX_WEIGHT + n - 2
        else:
            for v in range(1, n - 1):
                f.write(f"0 {v} 1\n{v} {n - 1} 1\n")
            distance = 2
        # Zero-cost self-loops have no effect on shortest path distances.
        # Spread them over interior vertices so the padding does not create a
        # single artificial high-degree hub.
        for i in range(m - minimum):
            v = 1 + i % (n - 2)
            f.write(f"{v} {v} 0\n")
    heavy = min(heavy, q)
    with (data / "queries.txt").open("w", encoding="ascii") as f:
        for _ in range(heavy):
            f.write(f"0 {n - 1}\n")
        for i in range(q - heavy):
            v = i % n
            f.write(f"{v} {v}\n")
    return (f"{distance}\n" * heavy + "0\n" * (q - heavy)).encode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shape", choices=("chain", "broad"), default="chain")
    parser.add_argument("--n", type=int, default=1_740_512)
    parser.add_argument("--m", type=int, default=5_000_000)
    parser.add_argument("--q", type=int, default=2_000)
    parser.add_argument("--heavy", type=int, default=12,
                        help="number of repeated nontrivial queries, capped at q")
    parser.add_argument("--binary", action="append", required=True,
                        help="absolute or relative executable path; repeat to compare")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--probe-script", type=Path,
                        help="run one instrumented binary through this diagnostic script")
    parser.add_argument("--threads", type=int, default=12,
                        help="diagnostic-only worker count passed to the probe")
    parser.add_argument("--min-wide-active", type=int, default=1)
    parser.add_argument("--min-wide-runs", type=int, default=1)
    parser.add_argument("--min-narrow-touch", type=int, default=0)
    parser.add_argument("--min-wide-touch", type=int, default=0)
    parser.add_argument("--barrier-at", type=int, default=0,
                        help="hold all diagnostic workers after this many wide-search touches")
    parser.add_argument("--barrier-timeout", type=int, default=90,
                        help="maximum seconds a worker waits at the diagnostic barrier")
    parser.add_argument("--require-cutoff", action="store_true")
    parser.add_argument("--require-exhaustion", action="store_true")
    args = parser.parse_args()
    if args.probe_script and len(args.binary) != 1:
        parser.error("--probe-script requires exactly one --binary")
    if args.probe_script and not 1 <= args.threads <= 12:
        parser.error("diagnostic --threads must be between 1 and 12")
    if min(args.min_wide_active, args.min_wide_runs,
           args.min_narrow_touch, args.min_wide_touch, args.barrier_at) < 0:
        parser.error("diagnostic minimums must be nonnegative")
    if not args.probe_script and (args.require_cutoff or args.require_exhaustion or args.barrier_at):
        parser.error("diagnostic assertions require --probe-script")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if not 1 <= args.barrier_timeout <= 300:
        parser.error("--barrier-timeout must be between 1 and 300 seconds")
    if args.barrier_at and (args.barrier_at > args.n or min(args.heavy, args.q) < args.threads):
        parser.error("barrier requires at least one heavy query per worker and threshold <= n")
    if args.barrier_at and args.barrier_timeout >= args.timeout:
        parser.error("--barrier-timeout must be smaller than --timeout")
    binaries = [Path(name).resolve(strict=True) for name in args.binary]
    with tempfile.TemporaryDirectory(prefix="sd-d-fulltouch-") as tmp:
        root = Path(tmp)
        data = root / "data"
        expected = generate(data, args.shape, args.n, args.m, args.q, args.heavy)
        digest = hashlib.sha256(expected).hexdigest()
        print(f"shape={args.shape} n={args.n} m={args.m} q={args.q} "
              f"heavy={min(args.heavy, args.q)} expected_sha256={digest}", flush=True)
        if args.probe_script:
            probe = args.probe_script.resolve(strict=True)
            cmd = [sys.executable, str(probe), "--binary", str(binaries[0]),
                   "--data", str(data), "--shape", args.shape,
                   "--threads", str(args.threads),
                   "--min-wide-active", str(args.min_wide_active),
                   "--min-wide-runs", str(args.min_wide_runs),
                   "--min-narrow-touch", str(args.min_narrow_touch),
                   "--min-wide-touch", str(args.min_wide_touch),
                   "--barrier-at", str(args.barrier_at),
                   "--barrier-timeout", str(args.barrier_timeout),
                   "--timeout", str(args.timeout)]
            if args.require_cutoff:
                cmd.append("--require-cutoff")
            if args.require_exhaustion:
                cmd.append("--require-exhaustion")
            # probe enforces the inner timeout and kills its direct binary;
            # allow it a little extra time to report before terminating probe.
            subprocess.run(cmd, check=True, timeout=args.timeout + 5)
            return
        for i, binary in enumerate(binaries):
            out = root / f"out-{i}"
            out.mkdir()
            env = {**os.environ, "SD_DATA": str(data), "SD_OUT": str(out)}
            started = time.monotonic()
            subprocess.run([str(binary)], check=True, env=env, timeout=args.timeout)
            elapsed = time.monotonic() - started
            actual = (out / "distances.txt").read_bytes()
            if actual != expected:
                raise AssertionError(f"{binary}: wrong distances, sha256="
                                     f"{hashlib.sha256(actual).hexdigest()}")
            print(f"PASS {binary} wall_s={elapsed:.6f} sha256={digest}", flush=True)


if __name__ == "__main__":
    main()

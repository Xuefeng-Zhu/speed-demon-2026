#!/usr/bin/env python3
"""Interleaved wall-time A/B for Track B binaries on the VM.

bench.py [-n ROUNDS] [-s SEEDS] [--mem] bin1 bin2 ...
Each round runs every binary once on each seed, in a random order, pinned to
CPUs 0-11 (6 cores x 2 threads, like the board), and checks the output hash.
--mem runs each binary in a fresh cgroup and reports memory.peak.
"""
import argparse, hashlib, os, random, statistics, subprocess, sys, time

K = os.path.expanduser('~/kiro-b')
EXPECTED = {1: 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927',
            2: '7f224ef65795253d56911fa8f25553a8fd0a2cef4addc7bd411e40e8da990869'}


def run(binary, seed, mem, threads, cpus):
    out = f'/dev/shm/kb-out-{os.path.basename(binary)}'
    os.makedirs(out, exist_ok=True)
    res = os.path.join(out, 'results.txt')
    if os.path.exists(res):
        os.unlink(res)
    env = dict(os.environ, SD_DATA=f'{K}/data/s{seed}', SD_OUT=out)
    if threads:
        env['SD_THREADS'] = str(threads)
    peak = None
    if mem:
        cg = f'/sys/fs/cgroup/kb{os.getpid()}'
        script = (f'mkdir -p {cg}; echo $$ > {cg}/cgroup.procs; '
                  f'setpriv --reuid={os.getuid()} --regid={os.getgid()} --clear-groups '
                  f'env SD_DATA={env["SD_DATA"]} SD_OUT={out} {"SD_THREADS=" + str(threads) if threads else ""} '
                  f'taskset -c {cpus} {binary}; s=$?; cat {cg}/memory.peak; '
                  f'echo $$ > /sys/fs/cgroup/cgroup.procs; rmdir {cg}; exit $s')
        t0 = time.perf_counter_ns()
        p = subprocess.run(['sudo', '-n', 'bash', '-c', script], capture_output=True, text=True)
        wall = time.perf_counter_ns() - t0
        if p.returncode:
            sys.exit(f'{binary} seed {seed}: exit {p.returncode}\n{p.stderr[-2000:]}')
        peak = int(p.stdout.split()[-1])
    else:
        t0 = time.perf_counter_ns()
        pid = os.posix_spawn('/usr/bin/taskset', ['taskset', '-c', cpus, binary], env)
        _, status, ru = os.wait4(pid, 0)
        wall = time.perf_counter_ns() - t0
        if status:
            sys.exit(f'{binary} seed {seed}: status {status}')
    h = hashlib.sha256(open(res, 'rb').read()).hexdigest()
    if h != EXPECTED[seed]:
        sys.exit(f'{binary} seed {seed}: WRONG OUTPUT {h}')
    return wall / 1e6, peak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=10)
    ap.add_argument('-s', default='1')
    ap.add_argument('-t', type=int, default=0, help='SD_THREADS (default: affinity)')
    ap.add_argument('--cpus', default='0-11')
    ap.add_argument('--mem', action='store_true')
    ap.add_argument('bins', nargs='+')
    a = ap.parse_args()
    seeds = [int(x) for x in a.s.split(',')]
    bins = [b if '/' in b else f'{K}/bin/{b}' for b in a.bins]
    for seed in seeds:  # warm the page cache
        for f in ('docs.txt', 'queries.txt'):
            open(f'{K}/data/s{seed}/{f}', 'rb').read()
    times = {(b, s): [] for b in bins for s in seeds}
    peaks = {(b, s): [] for b in bins for s in seeds}
    rng = random.Random()
    for b in bins:  # one discarded warm-up each
        run(b, seeds[0], False, a.t, a.cpus)
    for r in range(a.n):
        for s in seeds:
            order = bins[:]
            rng.shuffle(order)
            for b in order:
                w, p = run(b, s, a.mem, a.t, a.cpus)
                times[(b, s)].append(w)
                if p:
                    peaks[(b, s)].append(p)
    for s in seeds:
        base = times[(bins[0], s)]
        print(f'seed {s}, {a.n} rounds')
        for b in bins:
            t = times[(b, s)]
            pair = [100 * (x / y - 1) for x, y in zip(t, base)]
            mem = f' peak {max(peaks[(b, s)]) / 1e6:.1f} MB (med {statistics.median(peaks[(b, s)]) / 1e6:.1f})' if peaks[(b, s)] else ''
            print(f'  {os.path.basename(b):24s} med {statistics.median(t):7.1f} ms  min {min(t):7.1f}  '
                  f'paired {statistics.median(pair):+6.2f}%{mem}')


main()

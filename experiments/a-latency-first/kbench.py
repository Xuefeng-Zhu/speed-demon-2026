#!/usr/bin/env python3
"""Interleaved, hash-checked wall-time (and optional cgroup peak) A/B for any track on the VM.
kbench.py TRACK [-n ROUNDS] [-s SEEDS] [-t THREADS] [--mem] [--tmpfs] bin1 bin2 ...
Each round runs every binary once per seed in random order, pinned to CPUs 0-11 (6 cores x 2
threads, like the board's cpuset), and checks the output's SHA-256 against expected.json
(TRACK/seed -> hash). --mem runs each binary in a fresh cgroup and reports memory.peak.
Output goes to /dev/shm (tmpfs, like the board's /out), deleted before each run.
"""
import argparse, hashlib, json, os, random, statistics, subprocess, sys, time
K = os.path.expanduser('~/kiro-k2')
FILES = {'a': (['requests.log'], 'summary.txt'), 'b': (['docs.txt', 'queries.txt'], 'results.txt'),
         'c': (['records.csv', 'regions.csv'], 'aggregates.txt'), 'd': (['graph.txt', 'queries.txt'], 'distances.txt')}
EXP = json.load(open(f'{K}/expected.json')) if os.path.exists(f'{K}/expected.json') else {}

def run(track, binary, seed, mem, threads, cpus, check=True):
    out = f'/dev/shm/kk-out-{os.getpid()}-{os.path.basename(binary)}'
    os.makedirs(out, exist_ok=True)
    res = os.path.join(out, FILES[track][1])
    if os.path.exists(res):
        os.unlink(res)
    data = f'{K}/data/{track}/full-seed{seed}'
    env = dict(os.environ, SD_DATA=data, SD_OUT=out)
    if threads:
        env['SD_THREADS'] = str(threads)
    peak = None
    if mem:
        cg = f'/sys/fs/cgroup/kk{os.getpid()}'
        script = (f'mkdir -p {cg}; echo $$ > {cg}/cgroup.procs; '
                  f'setpriv --reuid={os.getuid()} --regid={os.getgid()} --clear-groups '
                  f'env SD_DATA={data} SD_OUT={out} {"SD_THREADS=" + str(threads) if threads else ""} '
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
    key = f'{track}/{seed}'
    if check and key in EXP and h != EXP[key]:
        sys.exit(f'{binary} seed {seed}: WRONG OUTPUT {h}')
    os.unlink(res)
    return wall / 1e6, peak, h

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('track')
    ap.add_argument('-n', type=int, default=10)
    ap.add_argument('-s', default='1')
    ap.add_argument('-t', type=int, default=0, help='SD_THREADS (default: affinity)')
    ap.add_argument('--cpus', default='0-11')
    ap.add_argument('--mem', action='store_true')
    ap.add_argument('--nocheck', action='store_true')
    ap.add_argument('bins', nargs='+')
    a = ap.parse_args()
    seeds = [int(x) for x in a.s.split(',')]
    bins = [os.path.abspath(b) for b in a.bins]
    for seed in seeds:  # warm the page cache outside the measured cgroup
        for f in FILES[a.track][0]:
            open(f'{K}/data/{a.track}/full-seed{seed}/{f}', 'rb').read()
    times = {(b, s): [] for b in bins for s in seeds}
    peaks = {(b, s): [] for b in bins for s in seeds}
    rng = random.Random()
    for b in bins:  # one discarded warm-up each
        run(a.track, b, seeds[0], False, a.t, a.cpus, check=not a.nocheck)
    for r in range(a.n):
        for s in seeds:
            order = bins[:]
            rng.shuffle(order)
            for b in order:
                w, p, _ = run(a.track, b, s, a.mem, a.t, a.cpus, check=not a.nocheck)
                times[(b, s)].append(w)
                if p:
                    peaks[(b, s)].append(p)
    for s in seeds:
        base = times[(bins[0], s)]
        print(f'track {a.track} seed {s}, {a.n} rounds, threads {a.t or "auto"}')
        for b in bins:
            t = times[(b, s)]
            pair = [100 * (x / y - 1) for x, y in zip(t, base)]
            mem = f' peak max {max(peaks[(b, s)]) / 1e6:.2f} MB med {statistics.median(peaks[(b, s)]) / 1e6:.2f}' if peaks[(b, s)] else ''
            print(f'  {os.path.basename(b):22s} med {statistics.median(t):8.2f} ms  min {min(t):8.2f}  '
                  f'paired {statistics.median(pair):+6.2f}%{mem}')
main()

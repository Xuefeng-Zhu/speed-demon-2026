#!/usr/bin/env python3
"""Run a timeline-instrumented Track B binary and summarise where wall time goes.

tlrun.py [-n RUNS] [-t THREADS] [--cpus LIST] [--seed S] binary
Prints, for the median run by wall time: startup, each serial phase, the worker
phase (scan, wait, answer, idle tail per thread, per-thread CPU and faults), the
output phase and the exit cost. Also prints medians over all runs.
"""
import argparse, hashlib, os, statistics, time

K = os.path.expanduser('~/kiro-b')
EXPECTED = {1: 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927',
            2: '7f224ef65795253d56911fa8f25553a8fd0a2cef4addc7bd411e40e8da990869'}


def one(binary, threads, cpus, seed):
    out = '/dev/shm/kb-tl'
    os.makedirs(out, exist_ok=True)
    err = f'{out}/stderr.txt'
    env = dict(os.environ, SD_DATA=f'{K}/data/s{seed}', SD_OUT=out)
    if threads:
        env['SD_THREADS'] = str(threads)
    fd = os.open(err, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    t0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    env['KB_T0'] = str(t0)
    pid = os.posix_spawn('/usr/bin/taskset', ['taskset', '-c', cpus, binary], env,
                         file_actions=[(os.POSIX_SPAWN_DUP2, fd, 2)])
    _, status, ru = os.wait4(pid, 0)
    end = (time.clock_gettime_ns(time.CLOCK_MONOTONIC) - t0) / 1e6
    os.close(fd)
    assert status == 0, status
    h = hashlib.sha256(open(f'{out}/results.txt', 'rb').read()).hexdigest()
    assert h == EXPECTED[seed], 'wrong output'
    ev = []
    for line in open(err):
        p = line.split()
        if p and p[0] == 'EV':
            ev.append((p[1], int(p[2]), int(p[3]), int(p[4]) / 1e6, int(p[5]), int(p[6]), int(p[7])))
    return {'end': end, 'ev': ev, 'utime': ru.ru_utime * 1e3, 'stime': ru.ru_stime * 1e3,
            'minflt': ru.ru_minflt, 'nvcsw': ru.ru_nvcsw, 'nivcsw': ru.ru_nivcsw}


def summarise(r):
    ev, end = r['ev'], r['end']
    t = {}
    for l, tid, c, ms, *_ in ev:
        if tid == 99:
            t[l] = ms
    rows = {}
    rows['startup (spawn to main)'] = t['main']
    rows['parse + intern'] = t['parsed'] - t['main']
    rows['map docs'] = t['mapped'] - t['parsed']
    rows['filter build'] = t['filter'] - t['mapped']
    rows['sample scan'] = t['sampled'] - t['filter']
    rows['plan (renumber, phrases, cuts)'] = t['planned'] - t['sampled']
    workers = sorted({tid for l, tid, *_ in ev if l == 'w_start'})
    ws = {w: next(ms for l, tid, c, ms, *_ in ev if l == 'w_start' and tid == w) for w in workers}
    we = {w: next(ms for l, tid, c, ms, *_ in ev if l == 'w_end' and tid == w) for w in workers}
    rows['worker phase (planned to joined)'] = t['joined'] - t['planned']
    rows['output format (12 threads)'] = t['formatted'] - t['joined']
    rows['output write'] = t['written'] - t['formatted']
    rows['print log + exit + reap'] = end - t['written']
    # Per-worker accounting inside the worker phase.
    scan = {w: 0.0 for w in workers}
    wait = {w: 0.0 for w in workers}
    ans = {w: 0.0 for w in workers}
    nchunk = {w: 0 for w in workers}
    last = {}
    for l, tid, c, ms, *_ in ev:
        if tid not in scan:
            continue
        if l == 'c_claim':
            last[tid] = ms
        elif l == 'c_scanned':
            scan[tid] += ms - last[tid]; last[tid] = ms; nchunk[tid] += 1
        elif l == 'c_waited':
            wait[tid] += ms - last[tid]; last[tid] = ms
        elif l == 'c_answered':
            ans[tid] += ms - last[tid]; last[tid] = ms
    cpu = {}
    flt = {}
    for w in workers:
        a = next(e for e in ev if e[0] == 'w_start' and e[1] == w)
        b = next(e for e in ev if e[0] == 'w_end' and e[1] == w)
        cpu[w] = ((b[4] - a[4]) + (b[5] - a[5])) / 1e3, (b[5] - a[5]) / 1e3
        flt[w] = b[6] - a[6]
    jmax = max(we.values())
    st = [e for e in ev if e[0] in ('s_start', 's_end')]
    detail = {
        'worker start spread': max(ws.values()) - min(ws.values()),
        'first worker start after planned': min(ws.values()) - t['planned'],
        'setup thread span': st[1][3] - st[0][3] if len(st) == 2 else float('nan'),
        'scan per worker (mean)': statistics.mean(scan.values()),
        'answer per worker (mean)': statistics.mean(ans.values()),
        'wait for setup per worker (mean)': statistics.mean(wait.values()),
        'idle tail per worker (mean, last end - own end)': statistics.mean(jmax - we[w] for w in workers),
        'idle tail max': max(jmax - we[w] for w in workers),
        'worker CPU (user+sys, mean)': statistics.mean(c[0] for c in cpu.values()),
        'worker sys CPU (mean)': statistics.mean(c[1] for c in cpu.values()),
        'worker minor faults (sum)': sum(flt.values()),
        'chunks per worker': '/'.join(str(nchunk[w]) for w in workers),
    }
    return rows, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=5)
    ap.add_argument('-t', type=int, default=0)
    ap.add_argument('--cpus', default='0-11')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('binary')
    a = ap.parse_args()
    b = a.binary if '/' in a.binary else f'{K}/bin/{a.binary}'
    for f in ('docs.txt', 'queries.txt'):
        open(f'{K}/data/s{a.seed}/{f}', 'rb').read()
    one(b, a.t, a.cpus, a.seed)  # warm-up
    runs = [one(b, a.t, a.cpus, a.seed) for _ in range(a.n)]
    sums = [summarise(r) for r in runs]
    print(f'{os.path.basename(b)} threads={a.t or "auto"} cpus={a.cpus} seed={a.seed}: '
          f'wall median {statistics.median(r["end"] for r in runs):.1f} ms over {a.n} runs; '
          f'process CPU user {statistics.median(r["utime"] for r in runs):.0f} ms, '
          f'sys {statistics.median(r["stime"] for r in runs):.0f} ms, '
          f'minor faults {statistics.median(r["minflt"] for r in runs):.0f}, '
          f'involuntary switches {statistics.median(r["nivcsw"] for r in runs):.0f}')
    for key in sums[0][0]:
        print(f'  {key:40s} {statistics.median(s[0][key] for s in sums):8.2f} ms')
    for key in sums[0][1]:
        vals = [s[1][key] for s in sums]
        if isinstance(vals[0], str):
            print(f'    {key:46s} {vals[0]}')
        else:
            print(f'    {key:46s} {statistics.median(vals):8.2f}')


main()

#!/usr/bin/env python3
"""Paired runs of Track B binaries under a heterogeneity emulation (local sandbox only).

    python3 emu.py --base B --cand C --layout p20 --pairs 11 --report r.json

Each pair runs the base and the candidate once, in alternating order (base first in even
pairs), after one warmup pair. Every run is checked against the seed-1 SHA-256. The
report has 'runs' (candidate) and 'baseline_runs' like experiments/b-linux-profile/run.py
reports, so experiments/b-filter-parse/pair.py reads it too.

Layouts (8 vCPUs here: cores 0-3, SMT siblings c and c + 4). "P" workers stand for
P-core threads, "E" workers for E-core threads; the E/P CPU-time share is the nominal
speed ratio (the README reports the measured one):
  plain8   SD_THREADS=8, no pinning, no spinners (the plain sandbox run).
  plain12  SD_THREADS=12, no pinning (oversubscribed but fair).
  u20      SD_THREADS=20, no pinning (oversubscribed but fair).
  s20      SD_THREADS=20, no pinning, nice-0 spinner processes pinned on vCPUs 3 and 7.
  p20      SD_THREADS=20. Workers 0-11 (P) two per vCPU on 0,1,2,4,5,6 (cores 0-2);
           workers 12-19 (E) four per vCPU on 3,7 (core 3). E/P = (1/4)/(1/2) = 0.5.
  m20      p20 plus a nice-2 spinner on each P vCPU: P share 1024/(2048+655) = 0.38,
           E 0.25, E/P = 0.66.
  p12      SD_THREADS=12. Workers 0-5 (P) one per vCPU on 0,1,2,4,5,6, each sharing it
           with a nice-3 spinner (P share 1024/1550 = 0.66); workers 6-11 (E) three per
           vCPU on 3,7 (1/3). E/P = 0.5.
  m12      as p12 with nice-0 spinners: P 0.5, E 0.33, E/P = 0.67.
The pinning is done by the LD_PRELOAD shim pin.so (SD_EMU_CPUS), so production binaries
run unmodified. The main thread is never pinned.
"""
import argparse, json, os, pathlib, random, signal, statistics as st, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'b-linux-profile'))
import run as R  # noqa: E402  (parse_stderr, sum_idx, sha256_file, EXPECTED)
R.TAGS = R.TAGS + ('MEMK',)

P6 = [0, 1, 2, 4, 5, 6]
# name: (threads, worker CPUs or None, spinners as (cpu, nice), number of P workers)
LAYOUTS = {
    'plain8': (8, None, [], 8),
    'plain12': (12, None, [], 12),
    'u20': (20, None, [], 20),
    's20': (20, None, [(3, 0), (7, 0)], 20),
    'p20': (20, P6 + P6 + [3, 7] * 4, [], 12),
    'm20': (20, P6 + P6 + [3, 7] * 4, [(c, 2) for c in P6], 12),
    'p12': (12, P6 + [3, 7] * 3, [(c, 3) for c in P6], 6),
    'm12': (12, P6 + [3, 7] * 3, [(c, 0) for c in P6], 6),
}


def boot(x, n=2000, seed=1):
    """95% bootstrap interval of the median of x."""
    rng = random.Random(seed)
    ms = sorted(st.median(rng.choices(x, k=len(x))) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def spin(spec):
    return [subprocess.Popen(['nice', '-n', str(n), 'taskset', '-c', str(c), 'sh', '-c', 'while :; do :; done'])
            for c, n in spec]


def cpu_idle(rows, lo, hi, cpus, ncpu=8):
    """Share of vCPU time in the index window [lo, hi] with no busy worker: with pinning a
    vCPU is busy while any worker pinned to it is inside a chunk; without, min(ncpu, busy
    workers) vCPUs are busy."""
    ev = []
    for x in rows:
        t, t0, t1 = x[0], x[4], x[6]
        ev += [(t0, 1, t), (t1, -1, t)]
    ev.sort()
    act, prev, busy = {}, lo, 0.0
    def nbusy():
        if cpus:
            return len({cpus[t] for t, n in act.items() if n > 0})
        return min(ncpu, sum(n > 0 for n in act.values()))
    for ts, d, t in ev:
        busy += nbusy() * (ts - prev)
        prev = ts
        act[t] = act.get(t, 0) + d
    busy += nbusy() * (hi - prev)
    return 1 - busy / (ncpu * (hi - lo))


def speeds(rows, np_):
    """Median scan speed (MB/s of wall time inside chunks) of the P and the E workers."""
    by = {}
    for x in rows:
        a = by.setdefault(x[0], [0, 0])
        a[0] += x[3]; a[1] += x[6] - x[4]
    sp = {t: b / ns * 1e3 for t, (b, ns) in by.items() if ns}
    p = [v for t, v in sp.items() if t < np_]
    e = [v for t, v in sp.items() if t >= np_]
    return st.median(p) if p else None, st.median(e) if e else None


def run_once(binary, data, out, threads, cpus, np_, extra=None):
    res = pathlib.Path(out) / 'results.txt'
    if res.exists():
        res.unlink()
    env = {k: v for k, v in os.environ.items() if not k.startswith('SD_')}
    env.update({'SD_DATA': data, 'SD_OUT': out, 'SD_THREADS': str(threads)})
    env.update(extra or {})
    if cpus:
        env['LD_PRELOAD'] = str(pathlib.Path(os.environ.get('CH2', '/projects/sandbox/.data/ch2')) / 'pin.so')
        env['SD_EMU_CPUS'] = ','.join(map(str, cpus))
    with tempfile.TemporaryFile() as err:
        t0 = time.monotonic()
        pid = os.posix_spawn(binary, [binary], env, file_actions=[(os.POSIX_SPAWN_DUP2, err.fileno(), 2)])
        _, status, ru = os.wait4(pid, 0)
        wall = time.monotonic() - t0
        err.seek(0)
        stderr = err.read().decode(errors='replace')
    if os.waitstatus_to_exitcode(status) != 0:
        raise RuntimeError(stderr[-2000:])
    h = R.sha256_file(res)
    if h != R.EXPECTED:
        raise RuntimeError(f'hash mismatch {h}')
    instr, parsed, _ = R.parse_stderr(stderr)
    r = {'threads': threads, 'wall_s': wall, 'user_s': ru.ru_utime, 'sys_s': ru.ru_stime,
         'cpu_s': ru.ru_utime + ru.ru_stime, 'maxrss_kib': ru.ru_maxrss, 'minflt': ru.ru_minflt,
         'nivcsw': ru.ru_nivcsw, 'instr': instr}
    if 'IDX' in parsed and 'PHASE' in parsed:
        r['idx'] = R.sum_idx([{'parsed': parsed}])
        ph = R.phase_durations({'parsed': parsed})
        r['phase_ms'] = ph
        # Per-thread end and busy, and the share of index thread-time spent idle.
        ix = r['idx']['index']
        ts = R.phase_ts({'parsed': parsed})
        sp, se = speeds(parsed['IDX'], np_)
        r['tail'] = {'index_ms': ph['index'], 'answer_ms': ph.get('answer'),
                     'cpu_idle_frac': cpu_idle(parsed['IDX'], ts['rows_alloc'], ts['index'], cpus),
                     'thread_idle_frac': 1 - ix['utilization'], 'idle_tail_ms': ix['idle_tail_ms'],
                     'chunks': ix['chunks'], 'p_mb_s': sp}
        if se:
            r['tail'].update({'e_mb_s': se, 'e_over_p': se / sp})
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', required=True)
    p.add_argument('--cand', required=True)
    p.add_argument('--layout', default='p20', choices=sorted(LAYOUTS))
    p.add_argument('--pairs', type=int, default=11)
    p.add_argument('--data', default='/projects/sandbox/.data/speed-b-full')
    p.add_argument('--report', required=True)
    a = p.parse_args()
    threads, cpus, spins, np_ = LAYOUTS[a.layout]
    base, cand = os.path.abspath(a.base), os.path.abspath(a.cand)
    out = tempfile.mkdtemp(prefix='emu-', dir=os.environ.get('CH2', '/projects/sandbox/.data/ch2'))
    sp = spin(spins)
    rows, brows = [], []
    try:
        time.sleep(0.3 if sp else 0)
        for i in range(-1, a.pairs):
            order = [(base, brows), (cand, rows)]
            if i % 2:
                order.reverse()
            for b, dest in order:
                r = run_once(b, a.data, out, threads, cpus, np_)
                r['run'], r['warmup'] = i, i < 0
                dest.append(r)
            print(f"pair {i}: base {brows[-1]['wall_s']*1e3:.1f} cand {rows[-1]['wall_s']*1e3:.1f} ms", flush=True)
    finally:
        for s in sp:
            s.send_signal(signal.SIGKILL)
            s.wait()
        for f in pathlib.Path(out).iterdir():
            f.unlink()
        os.rmdir(out)
    c = [r for r in rows if not r['warmup']]
    b = [r for r in brows if not r['warmup']]
    dw = [x['wall_s'] / y['wall_s'] - 1 for x, y in zip(c, b)]
    dc = [x['cpu_s'] / y['cpu_s'] - 1 for x, y in zip(c, b)]
    summ = {'layout': a.layout, 'threads': threads, 'cpus': cpus, 'spinners': spins, 'pairs': len(c),
            'paired_wall_pct': 100 * st.median(dw), 'ci95_pct': [100 * v for v in boot(dw)],
            'wins': sum(x < 0 for x in dw),
            'paired_cpu_pct': 100 * st.median(dc),
            'cand_wall_ms': 1e3 * st.median(r['wall_s'] for r in c), 'base_wall_ms': 1e3 * st.median(r['wall_s'] for r in b),
            'cand_cpu_ms': 1e3 * st.median(r['cpu_s'] for r in c), 'base_cpu_ms': 1e3 * st.median(r['cpu_s'] for r in b),
            'cand_rss_kib': st.median(r['maxrss_kib'] for r in c), 'base_rss_kib': st.median(r['maxrss_kib'] for r in b)}
    for name, rs in (('cand', c), ('base', b)):
        if all('tail' in r for r in rs):
            summ[name + '_tail'] = {k: st.median(r['tail'][k] for r in rs) for k in rs[0]['tail']}
    rep = {'note': 'local sandbox measurements, not official scores', 'summary': summ,
           'base_binary': base, 'base_sha256': R.sha256_file(base), 'cand_binary': cand,
           'cand_sha256': R.sha256_file(cand), 'runs': rows, 'baseline_runs': brows}
    pathlib.Path(a.report).write_text(json.dumps(rep, indent=1) + '\n')
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()

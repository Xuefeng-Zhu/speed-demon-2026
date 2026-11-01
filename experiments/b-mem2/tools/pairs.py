#!/usr/bin/env python3
"""pairs.py --threads T --runs N --report out.json base bin [bin ...]

Interleaved wall-time runs of Track B binaries on full seed 1 (no memory sampler, so no
sampling overhead): one warmup each, then N rounds; each round runs every binary once, in an
order rotated by the round number. The output SHA-256 is asserted on every run. Prints per
binary the median wall, the median of the per-round ratios to the first binary (paired delta),
the rounds it was faster, the median CPU delta and median minor faults (os.wait4).
Local sandbox measurements, not official scores. Bin names without '/' resolve to
/projects/sandbox/.data/bin/."""
import argparse, hashlib, json, os, shutil, statistics as st, subprocess, time

D = '/projects/sandbox/.data'
SHA = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'


def run(path, threads):
    out = '/dev/shm/pairs-out'
    shutil.rmtree(out, True)
    env = dict(os.environ, SD_DATA=f'{D}/b-full', SD_OUT=out, SD_THREADS=str(threads))
    t0 = time.perf_counter()
    p = subprocess.Popen([path], env=env)
    _, status, ru = os.wait4(p.pid, 0)
    wall = time.perf_counter() - t0
    assert status == 0, path
    h = hashlib.sha256(open(f'{out}/results.txt', 'rb').read()).hexdigest()
    assert h == SHA, (path, h)
    return {'wall_s': wall, 'cpu_s': ru.ru_utime + ru.ru_stime, 'minflt': ru.ru_minflt, 'maxrss_kib': ru.ru_maxrss}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threads', type=int, default=12)
    ap.add_argument('--runs', type=int, default=21)
    ap.add_argument('--report')
    ap.add_argument('bins', nargs='+')
    a = ap.parse_args()
    paths = [b if '/' in b else f'{D}/bin/{b}' for b in a.bins]
    for p in paths:
        run(p, a.threads)
    res = {b: [] for b in a.bins}
    for r in range(a.runs):
        k = r % len(paths)
        for i in list(range(k, len(paths))) + list(range(k)):
            res[a.bins[i]].append(run(paths[i], a.threads))
    base = res[a.bins[0]]
    summary = {}
    for b in a.bins:
        rs = res[b]
        dw = [x['wall_s'] / y['wall_s'] - 1 for x, y in zip(rs, base)]
        dc = [x['cpu_s'] / y['cpu_s'] - 1 for x, y in zip(rs, base)]
        s = {
            'wall_ms': st.median(x['wall_s'] for x in rs) * 1e3,
            'paired_wall_pct': st.median(dw) * 100,
            'wins': sum(x < 0 for x in dw),
            'paired_cpu_pct': st.median(dc) * 100,
            'minflt': st.median(x['minflt'] for x in rs),
            'maxrss_kib': st.median(x['maxrss_kib'] for x in rs),
        }
        summary[b] = s
        print(f"{b:18} t={a.threads} n={a.runs} wall {s['wall_ms']:6.1f} ms paired {s['paired_wall_pct']:+6.2f}% "
              f"(faster {s['wins']}/{a.runs}) cpu {s['paired_cpu_pct']:+6.2f}% minflt {s['minflt']:.0f} maxrss {s['maxrss_kib']:.0f} KiB")
    if a.report:
        json.dump({'threads': a.threads, 'runs': a.runs, 'bins': a.bins, 'summary': summary, 'raw': res,
                   'note': 'local sandbox measurements, not official scores'}, open(a.report, 'w'), indent=1)


main()

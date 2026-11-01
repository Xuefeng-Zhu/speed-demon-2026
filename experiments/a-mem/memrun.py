#!/usr/bin/env python3
"""memrun.py --track {a,b,c,d} [--runs N] [--threads T] [--data DIR] [--ref FILE] [--report out.json]
             [--env K=V ...] [--interval-us 200] bin [bin ...]

Runs one or more binaries of one track interleaved (round robin, after one warmup run of each),
checks the output on every run (published full seed-1 SHA-256 by default, or byte-compare with
--ref FILE, or the SHA-256 of --ref when it is a 64-hex string), and records per run:
  wall_s, cpu_s, ru_maxrss (os.wait4), sampled peaks from /proc/<pid>/status (every ~interval-us):
  RssAnon+RssShmem (peak of the sum), RssFile, VmPTE, VmRSS, plus output file size.
Estimated board M = peak(RssAnon+RssShmem) + output size (board M is a cgroup peak that charges
anon memory, page tables and the tmpfs output; mmapped input pages are not charged). That is an
upper bound, as the two peaks need not coincide; this copy (experiments/a-mem, from the round-4
tooling) adds live M = the peak over samples of RssAnon+RssShmem plus the output file's size at
the same moment.
est_M_pte adds the peak VmPTE too. Bin names without '/' resolve to /projects/sandbox/.data/bin/.
SD_OUT goes to a fresh dir under /dev/shm (tmpfs, like the board). Local sandbox measurements,
not official scores."""
import argparse, hashlib, json, os, shutil, statistics as st, sys, tempfile, time

D = '/projects/sandbox/.data'
TRACKS = {
    'a': ('summary.txt', '495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3'),
    'b': ('results.txt', 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'),
    'c': ('aggregates.txt', 'd8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536'),
    'd': ('distances.txt', 'a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e'),
}
KEYS = ('RssAnon', 'RssShmem', 'RssFile', 'VmPTE', 'VmRSS')


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def status(pid):
    try:
        with open(f'/proc/{pid}/status', 'rb') as f:
            txt = f.read()
    except OSError:
        return None
    v = {}
    for line in txt.split(b'\n'):
        k, _, rest = line.partition(b':')
        k = k.decode()
        if k in KEYS:
            v[k] = int(rest.split()[0])
    return v if 'RssAnon' in v else None


def one(binary, track, data, threads, extra, expect, interval):
    out = tempfile.mkdtemp(dir='/dev/shm', prefix='memrun-')
    env = dict(os.environ, SD_DATA=data, SD_OUT=out, **extra)
    if threads:
        env['SD_THREADS'] = str(threads)
    peak = {'anon_shmem': 0, 'RssAnon': 0, 'RssShmem': 0, 'RssFile': 0, 'VmPTE': 0, 'VmRSS': 0}
    nsamp, live = 0, 0
    op = os.path.join(out, TRACKS[track][0])
    with tempfile.TemporaryFile() as err:
        t0 = time.monotonic()
        pid = os.posix_spawn(binary, [binary], env, file_actions=[(os.POSIX_SPAWN_DUP2, err.fileno(), 2)])
        dt = interval / 1e6
        while True:
            v = status(pid)
            if v is None:
                break
            nsamp += 1
            s = v.get('RssAnon', 0) + v.get('RssShmem', 0)
            try:
                live = max(live, s * 1024 + os.stat(op).st_blocks * 512)
            except OSError:
                live = max(live, s * 1024)
            if s > peak['anon_shmem']:
                peak['anon_shmem'] = s
            for k in KEYS:
                if v.get(k, 0) > peak[k]:
                    peak[k] = v[k]
            time.sleep(dt)  # loop ends when the process is a zombie (no Rss lines left)
        _, stat, ru = os.wait4(pid, 0)
        wall = time.monotonic() - t0
        err.seek(0)
        etext = err.read().decode(errors='replace')
    code = os.waitstatus_to_exitcode(stat)
    if code != 0:
        shutil.rmtree(out, ignore_errors=True)
        raise SystemExit(f'{binary} exit {code}: {etext[-2000:]}')
    fn = TRACKS[track][0]
    op = os.path.join(out, fn)
    size = os.path.getsize(op)
    if expect['kind'] == 'file':
        with open(op, 'rb') as a, open(expect['v'], 'rb') as b:
            ok = a.read() == b.read()
        h = None
    else:
        h = sha_file(op)
        ok = h == expect['v']
    shutil.rmtree(out, ignore_errors=True)
    if not ok:
        raise SystemExit(f'OUTPUT MISMATCH {binary}: {h}')
    kb = 1024
    return {'wall_s': wall, 'cpu_s': ru.ru_utime + ru.ru_stime, 'maxrss_kib': ru.ru_maxrss,
            'minflt': ru.ru_minflt, 'samples': nsamp, 'peak_kib': peak, 'out_bytes': size,
            'est_M_mb': (peak['anon_shmem'] * kb + size) / 1e6,
            'live_M_mb': live / 1e6,
            'est_M_pte_mb': ((peak['anon_shmem'] + peak['VmPTE']) * kb + size) / 1e6, 'ok': True,
            'stderr_tail': etext[-500:]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--track', required=True, choices=sorted(TRACKS))
    ap.add_argument('--runs', type=int, default=11)
    ap.add_argument('--threads', type=int, default=0, help='set SD_THREADS (0 = leave unset)')
    ap.add_argument('--data', help='data dir (default /projects/sandbox/.data/<t>-full)')
    ap.add_argument('--ref', help='reference output file or expected sha256 (default: published full seed 1)')
    ap.add_argument('--report', help='write JSON report here')
    ap.add_argument('--env', action='append', default=[], help='extra K=V env for the binaries')
    ap.add_argument('--interval-us', type=float, default=200)
    ap.add_argument('--no-warmup', action='store_true')
    ap.add_argument('bins', nargs='+')
    a = ap.parse_args()
    data = a.data or f'{D}/{a.track}-full'
    if a.ref is None:
        expect = {'kind': 'sha', 'v': TRACKS[a.track][1]}
    elif len(a.ref) == 64 and all(c in '0123456789abcdef' for c in a.ref):
        expect = {'kind': 'sha', 'v': a.ref}
    else:
        expect = {'kind': 'file', 'v': a.ref}
    extra = dict(e.split('=', 1) for e in a.env)
    bins = [os.path.abspath(b) if '/' in b else f'{D}/bin/{b}' for b in a.bins]
    names = [os.path.basename(b) for b in bins]
    if len(set(names)) != len(names):
        names = bins
    runs = {n: [] for n in names}
    if not a.no_warmup:
        for b in bins:
            one(b, a.track, data, a.threads, extra, expect, a.interval_us)
    for i in range(a.runs):
        for b, n in zip(bins, names):
            runs[n].append(one(b, a.track, data, a.threads, extra, expect, a.interval_us))
    summary = {}
    med = lambda rs, f: st.median(f(r) for r in rs)
    for n, rs in runs.items():
        s = {'wall_ms_median': med(rs, lambda r: r['wall_s']) * 1e3,
             'wall_ms_min': min(r['wall_s'] for r in rs) * 1e3,
             'cpu_ms_median': med(rs, lambda r: r['cpu_s']) * 1e3,
             'maxrss_mb_median': med(rs, lambda r: r['maxrss_kib']) * 1024 / 1e6,
             'peak_anon_shmem_mb_median': med(rs, lambda r: r['peak_kib']['anon_shmem']) * 1024 / 1e6,
             'peak_anon_shmem_mb_max': max(r['peak_kib']['anon_shmem'] for r in rs) * 1024 / 1e6,
             'peak_file_mb_median': med(rs, lambda r: r['peak_kib']['RssFile']) * 1024 / 1e6,
             'peak_pte_kib_median': med(rs, lambda r: r['peak_kib']['VmPTE']),
             'out_mb': rs[0]['out_bytes'] / 1e6,
             'est_M_mb_median': med(rs, lambda r: r['est_M_mb']),
             'live_M_mb_median': med(rs, lambda r: r['live_M_mb']),
             'live_M_mb_max': max(r['live_M_mb'] for r in rs),
             'est_M_pte_mb_median': med(rs, lambda r: r['est_M_pte_mb']),
             'samples_median': med(rs, lambda r: r['samples'])}
        summary[n] = s
        print(f"{os.path.basename(n):22s} {a.track} t={a.threads or '-'} wall {s['wall_ms_median']:.1f} ms "
              f"(min {s['wall_ms_min']:.1f}) peak anon+shm {s['peak_anon_shmem_mb_median']:.2f} MB "
              f"(max {s['peak_anon_shmem_mb_max']:.2f}) file {s['peak_file_mb_median']:.1f} "
              f"maxrss {s['maxrss_mb_median']:.1f} out {s['out_mb']:.2f} est M {s['est_M_mb_median']:.2f} MB "
              f"(+pte {s['est_M_pte_mb_median']:.2f}) live M {s['live_M_mb_median']:.2f} (max {s['live_M_mb_max']:.2f})"
              f" samples {s['samples_median']:.0f}  output ok")
    if a.report:
        rep = {'note': 'local sandbox measurements, not official scores', 'track': a.track, 'data': data,
               'threads': a.threads, 'env': extra, 'runs_per_binary': a.runs, 'interval_us': a.interval_us,
               'binaries': {n: sha_file(b) for b, n in zip(bins, names)}, 'summary': summary, 'runs': runs}
        with open(a.report, 'w') as f:
            json.dump(rep, f, indent=1)


if __name__ == '__main__':
    main()

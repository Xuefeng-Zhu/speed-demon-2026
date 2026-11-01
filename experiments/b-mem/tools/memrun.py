#!/usr/bin/env python3
"""memrun.py --runs N --threads T --report out.json [--env K=V ...] bin [bin ...]

Runs memory-instrumented Track B binaries (made by mkmem.py) alternately on full seed 1, checks
the results.txt SHA-256 on every run, and saves per run: wall, ru_maxrss (os.wait4), the MEM
(/proc/self/status kB per phase), MALL (mallinfo2 KiB per phase), INFO and MIDX lines, and the
sampled MSAMP maximum when SD_PROF_SAMPLE_US is set. The summary has per-binary medians.
Local sandbox measurements, not official scores."""
import argparse, hashlib, json, os, statistics as st, tempfile, time, shutil

EXPECTED = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
D = '/projects/sandbox/.data'


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def one(binary, threads, env_extra):
    out = tempfile.mkdtemp(dir=D + '/mem')
    env = dict(os.environ, SD_DATA=D + '/speed-b-full', SD_OUT=out, SD_THREADS=str(threads), **env_extra)
    with tempfile.TemporaryFile() as err:
        t0 = time.monotonic()
        pid = os.posix_spawn(binary, [binary], env, file_actions=[(os.POSIX_SPAWN_DUP2, err.fileno(), 2)])
        _, status, ru = os.wait4(pid, 0)
        wall = time.monotonic() - t0
        err.seek(0)
        text = err.read().decode()
    assert os.waitstatus_to_exitcode(status) == 0, text[-2000:]
    h = sha(out + '/results.txt')
    shutil.rmtree(out)
    if h != EXPECTED:
        raise SystemExit(f'hash mismatch {binary}: {h}')
    r = {'wall_s': wall, 'maxrss_kib': ru.ru_maxrss, 'cpu_s': ru.ru_utime + ru.ru_stime, 'minflt': ru.ru_minflt,
         'mem': {}, 'mall': {}, 'info': {}, 'midx': [], 'samples_max_anon_kb': None}
    samp = []
    for line in text.splitlines():
        x = line.split()
        if not x:
            continue
        if x[0] == 'MEM':
            r['mem'][x[1]] = dict(zip(('VmHWM', 'VmRSS', 'RssAnon', 'RssFile'), map(int, x[2:6])))
        elif x[0] == 'MALL':
            r['mall'][x[1]] = dict(zip(('arena', 'hblks', 'hblkhd', 'uordblks', 'fordblks'), map(int, x[2:7])))
        elif x[0] == 'INFO':
            r['info'][x[1]] = int(x[2])
        elif x[0] == 'MIDX':
            r['midx'].append(line)
        elif x[0] == 'MSAMP':
            samp.append((int(x[1]), int(x[3])))
    if samp:
        t, a = max(samp, key=lambda s: s[1])
        r['samples_max_anon_kb'], r['samples_max_at_ms'] = a, t / 1e6
        r['phase_ns'] = {}
    for line in text.splitlines():
        x = line.split()
        if x and x[0] == 'PHASE':
            r.setdefault('phase_ns', {})[x[1]] = int(x[2])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=7)
    ap.add_argument('--threads', type=int, required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--env', action='append', default=[])
    ap.add_argument('bins', nargs='+')
    a = ap.parse_args()
    extra = dict(e.split('=', 1) for e in a.env)
    bins = [b if '/' in b else D + '/bin/' + b for b in a.bins]
    runs = {b: [] for b in bins}
    one(bins[0], a.threads, extra)  # warmup
    for _ in range(a.runs):
        for b in bins:
            runs[b].append(one(b, a.threads, extra))
    summary = {}
    for b, rs in runs.items():
        s = {'maxrss_kib_median': st.median(r['maxrss_kib'] for r in rs),
             'maxrss_kib_min': min(r['maxrss_kib'] for r in rs), 'maxrss_kib_max': max(r['maxrss_kib'] for r in rs),
             'wall_s_median': st.median(r['wall_s'] for r in rs), 'phase_mem_kb_median': {}}
        for ph in rs[0]['mem']:
            s['phase_mem_kb_median'][ph] = {k: st.median(r['mem'][ph][k] for r in rs if ph in r['mem'])
                                            for k in rs[0]['mem'][ph]}
        summary[os.path.basename(b)] = s
        print(f"{os.path.basename(b):20s} t={a.threads} {extra} maxrss med {s['maxrss_kib_median']:.0f} "
              f"[{s['maxrss_kib_min']}..{s['maxrss_kib_max']}] VmHWM med {s['phase_mem_kb_median']['write']['VmHWM']:.0f}")
    rep = {'note': 'local sandbox measurements, not official scores', 'threads': a.threads, 'env': extra,
           'runs_per_binary': a.runs, 'binaries': {os.path.basename(b): sha(b) for b in bins},
           'summary': summary, 'runs': {os.path.basename(b): rs for b, rs in runs.items()}}
    json.dump(rep, open(a.report, 'w'), indent=1)


if __name__ == '__main__':
    main()

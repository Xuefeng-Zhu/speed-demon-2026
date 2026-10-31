#!/usr/bin/env python3
"""Run a Track B binary repeatedly, verify the public seed-1 output, record wall time and
child rusage (os.wait4), and save raw observations plus medians as JSON.

No perf, valgrind, /usr/bin/time or cgroup memory.peak exist in the sandbox, so resource
numbers come from the kernel rusage of the exited child:
  ru_maxrss (KiB on Linux), ru_minflt, ru_majflt, ru_utime, ru_stime, ru_nvcsw, ru_nivcsw.

Optional instrumentation: every stderr line whose first token is a known tag
(PHASE, MEM, INFO, IDX, BLOCK, QTHREAD, SCAN, TSC, QKIND, QSLOW, SMAPS) is kept as raw
text and as a token list under run['instr'][TAG]. Binaries without instrumentation (the
production solution) simply produce no such lines. Lines with unknown tags are kept in
run['stderr_other']. Tag-specific parsing/summaries can be added to PARSERS/SUMMARIZERS.

Example:
  python3 run.py --binary ../../track-b/target/release/solution --data /tmp/speed-b-full \
      --runs 7 --report baseline-report.json
  python3 run.py --binary ... --data ... --threads 1,2,4,6,8 --runs 5 --report threads-report.json
"""
import argparse, hashlib, json, os, pathlib, platform, shutil, statistics, subprocess, tempfile, time

EXPECTED = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
TAGS = ('PHASE', 'MEM', 'INFO', 'IDX', 'BLOCK', 'QTHREAD', 'SCAN', 'TSC', 'QKIND', 'QSLOW', 'SMAPS')
# Per-tag parsers: tokens (after the tag) -> value stored in run['parsed'][TAG] list.
# Default keeps the tokens with integers converted. FEAT-002 can register richer parsers.
PARSERS = {}
# Per-tag summarizers: list of measured runs -> dict merged into the summary.
SUMMARIZERS = {}


def sha256_file(path, chunk=1 << 24):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def tok(x):
    try:
        return int(x)
    except ValueError:
        try:
            return float(x)
        except ValueError:
            return x


def parse_stderr(text):
    instr, parsed, other = {}, {}, []
    for line in text.splitlines():
        x = line.split()
        if x and x[0] in TAGS:
            instr.setdefault(x[0], []).append(line)
            f = PARSERS.get(x[0])
            parsed.setdefault(x[0], []).append(f(x[1:]) if f else [tok(t) for t in x[1:]])
        elif line.strip():
            other.append(line)
    return instr, parsed, other


def run_once(binary, data, out, threads):
    res = pathlib.Path(out) / 'results.txt'
    if res.exists():
        res.unlink()
    env = {**os.environ, 'SD_DATA': data, 'SD_OUT': out}
    env.pop('SD_THREADS', None)
    if threads is not None:
        env['SD_THREADS'] = str(threads)
    # stderr/stdout go to files, not pipes, so the child never blocks on a full pipe
    # and the parent does no work while the child runs.
    with tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as so:
        start = time.monotonic()
        pid = os.posix_spawn(binary, [binary], env,
                             file_actions=[(os.POSIX_SPAWN_DUP2, so.fileno(), 1),
                                           (os.POSIX_SPAWN_DUP2, err.fileno(), 2)])
        _, status, ru = os.wait4(pid, 0)
        wall = time.monotonic() - start
        err.seek(0); stderr = err.read().decode(errors='replace')
        so.seek(0); stdout = so.read().decode(errors='replace')
    code = os.waitstatus_to_exitcode(status)
    if code != 0:
        raise RuntimeError(f'exit {code}: {stderr[-2000:]}')
    h = sha256_file(res)
    assert h == EXPECTED, ('hash mismatch', h)
    instr, parsed, other = parse_stderr(stderr)
    return {
        'threads': threads, 'wall_s': wall, 'sha256': h,
        'user_s': ru.ru_utime, 'sys_s': ru.ru_stime, 'cpu_s': ru.ru_utime + ru.ru_stime,
        'maxrss_kib': ru.ru_maxrss, 'minflt': ru.ru_minflt, 'majflt': ru.ru_majflt,
        'nvcsw': ru.ru_nvcsw, 'nivcsw': ru.ru_nivcsw,
        'instr': instr, 'parsed': parsed, 'stderr_other': other, 'stdout': stdout,
    }


METRICS = ('wall_s', 'user_s', 'sys_s', 'cpu_s', 'maxrss_kib', 'minflt', 'majflt', 'nvcsw', 'nivcsw')


def summarize(measured):
    s = {'runs': len(measured)}
    for k in METRICS:
        v = [r[k] for r in measured]
        s['median_' + k] = statistics.median(v)
        s['min_' + k] = min(v)
        s['max_' + k] = max(v)
    s['median_cpu_util'] = statistics.median(r['cpu_s'] / r['wall_s'] for r in measured)
    for tag, f in SUMMARIZERS.items():
        if all(tag in r['parsed'] for r in measured):
            s.update(f(measured))
    return s


def environment(binary, data):
    def cmd(*c):
        try:
            return subprocess.run(c, capture_output=True, text=True).stdout.strip()
        except OSError:
            return None
    cpu = None
    try:
        for line in open('/proc/cpuinfo'):
            if line.startswith('model name'):
                cpu = line.split(':', 1)[1].strip(); break
    except OSError:
        pass
    return {
        'kernel': platform.release(), 'cpu_model': cpu, 'cpus': os.cpu_count(),
        'rustc': cmd('rustc', '--version'), 'python': platform.python_version(),
        'binary': str(binary), 'binary_sha256': sha256_file(binary),
        'data': str(data),
        'data_bytes': {n: os.path.getsize(os.path.join(data, n)) for n in ('docs.txt', 'queries.txt')},
        'note': 'local sandbox measurements, not official scores',
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--binary', required=True)
    p.add_argument('--data', required=True)
    p.add_argument('--runs', type=int, default=5, help='measured runs per thread setting')
    p.add_argument('--warmup', type=int, default=1, help='warmup runs per thread setting')
    p.add_argument('--threads', default=None, help='comma list, e.g. 1,2,4,6,8; default: binary default')
    p.add_argument('--out', default=None, help='SD_OUT directory (default: fresh temp dir in /tmp)')
    p.add_argument('--report', required=True)
    p.add_argument('--keep-stdout', action='store_true')
    a = p.parse_args()
    assert a.warmup >= 1 and a.runs >= 1
    binary = os.path.abspath(a.binary)
    settings = [None] if a.threads is None else [int(t) for t in a.threads.split(',')]
    out = a.out or tempfile.mkdtemp(prefix='sd-b-linux-profile-', dir='/tmp')
    os.makedirs(out, exist_ok=True)
    rows, summary = [], {}
    try:
        for t in settings:
            for run in range(-a.warmup, a.runs):
                r = run_once(binary, a.data, out, t)
                r['run'] = run; r['warmup'] = run < 0
                if not a.keep_stdout:
                    r.pop('stdout')
                rows.append(r)
                print(f"threads={t} run={run} wall={r['wall_s']:.3f}s cpu={r['cpu_s']:.3f}s "
                      f"maxrss={r['maxrss_kib']}KiB minflt={r['minflt']}", flush=True)
            measured = [r for r in rows if r['threads'] == t and not r['warmup']]
            summary['default' if t is None else str(t)] = summarize(measured)
    finally:
        if a.out is None:
            shutil.rmtree(out, ignore_errors=True)
    report = {'environment': environment(binary, a.data), 'expected_sha256': EXPECTED,
              'warmup': a.warmup, 'summary': summary, 'runs': rows}
    pathlib.Path(a.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

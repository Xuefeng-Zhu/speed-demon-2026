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
run['stderr_other']. Tag-specific parsing/summaries are in PARSERS/SUMMARIZERS; the
summarizers for the profile.rs / profile-scan.rs lines are defined below.

Example:
  python3 run.py --binary ../../track-b/target/release/solution --data /tmp/speed-b-full \
      --runs 7 --report baseline-report.json
  python3 run.py --binary ... --data ... --threads 1,2,4,6,8 --runs 5 --report threads-report.json
  python3 run.py --binary /tmp/prof --baseline /tmp/base --data ... --runs 7 --report report.json
      (--baseline runs an uninstrumented build alternately with --binary and reports overhead;
       --env KEY=VALUE passes e.g. SD_PROF_SMAPS=1 or SD_PROF_SAMPLE_US=1000 to the profiled binary)
"""
import argparse, hashlib, json, os, pathlib, platform, shutil, statistics, subprocess, tempfile, time

EXPECTED = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
TAGS = ('PHASE', 'MEM', 'INFO', 'IDX', 'BLOCK', 'QTHREAD', 'SCAN', 'TSC', 'QKIND', 'QSLOW', 'SMAPS', 'MEMT')
# Per-tag parsers: tokens (after the tag) -> value stored in run['parsed'][TAG] list.
# Default keeps the tokens with integers converted. FEAT-002 can register richer parsers.
PARSERS = {}
# Per-tag summarizers: list of measured runs -> dict merged into the summary.
SUMMARIZERS = {}

# ---------------------------------------------------------------------------
# Summaries of the profile.rs / profile-scan.rs lines (formats in README.md):
#   PHASE <name> <ns since main start>          end of a phase
#   MEM <phase> <VmHWM> <VmRSS> <RssAnon> <RssFile>   kB, /proc/self/status
#   SMAPS <phase> <Rss> <Pss> <Pss_Anon> <Pss_File> <Anonymous>   kB, smaps_rollup
#   MEMT <ns> <VmRSS> <RssAnon> <RssFile>       sampler thread (SD_PROF_SAMPLE_US)
#   INFO <key> <value>
#   IDX <thread> <chunk> <ndocs> <bytes> <t_start> <t_scan_end> <t_csr_end>
#       <stream_len> <stream_cap> <nhits> <docs_entries>
#   BLOCK <thread> <block> <nbool> <nphrase> <t_start> <t_end>
#   QTHREAD <thread> <bool_ns> <phrase_ns> <nbool> <nphrase>
#   QKIND <kind> <count> <total_ns> <max_ns> <clauses>
#   QSLOW <qi> <ns> <kind> <nclauses>
#   SCAN <thread> <chunk> <a> <b> <c> <d> <e> <f> <ntokens> <nanchors> <nhits> <ndocs>
#       <n_list> <n_bitmap> <n_none> <n_phrase_only> <n_long> <total>   (cycles)
#   TSC <cycles_per_ns> <cycles> <ns>
# Every summary value is the median over the measured runs of a per-run value.
# ---------------------------------------------------------------------------
PARALLEL_PHASES = ('index', 'answer')
SCAN_PARTS = ('masks', 'lookup', 'callback', 'phrase', 'release', 'csr')


def med(v):
    v = list(v)
    return statistics.median(v) if v else None


def med_dicts(ds):
    """Median of each key over a list of flat dicts of numbers."""
    keys = [k for k in ds[0] if all(k in d for d in ds)]
    return {k: med(d[k] for d in ds) for k in keys}


def phase_ts(r):
    return {p[0]: p[1] for p in r['parsed']['PHASE']}


def phase_durations(r):
    out, prev = {}, 0
    for name, t in r['parsed']['PHASE']:
        out[name] = (t - prev) / 1e6
        prev = t
    return out


def sum_phase(runs):
    per = []
    for r in runs:
        d = phase_durations(r)
        total = r['parsed']['PHASE'][-1][1] / 1e6
        par = sum(d.get(p, 0) for p in PARALLEL_PHASES)
        x = {f'{k}_ms': v for k, v in d.items()}
        x.update({'main_total_ms': total, 'outside_main_ms': r['wall_s'] * 1e3 - total,
                  'parallel_ms': par, 'serial_ms': total - par, 'parallel_frac': par / total,
                  'serial_frac': (total - par) / total})
        per.append(x)
    return {'phase_ms': med_dicts(per), 'phase_order': [p[0] for p in runs[0]['parsed']['PHASE']]}


def sum_mem(runs, tag, fields):
    out = {}
    for name in [m[0] for m in runs[0]['parsed'][tag]]:
        rows = [[m for m in r['parsed'][tag] if m[0] == name][-1] for r in runs]
        out[name] = {f: med(row[i + 1] for row in rows) for i, f in enumerate(fields)}
    return out


def sum_idx(runs):
    per, by_thread = [], {}
    for r in runs:
        ts = phase_ts(r)
        lo, hi = ts['rows_alloc'], ts['index']
        rows = r['parsed']['IDX']
        th = {}
        for (t, k, nd, nb, t0, t1, t2, sl, sc, nh, de) in [x[:11] for x in rows]:
            a = th.setdefault(t, {'busy': 0, 'scan': 0, 'csr': 0, 'first': t0, 'last': t2, 'chunks': 0, 'bytes': 0})
            a['busy'] += t2 - t0; a['scan'] += t1 - t0; a['csr'] += t2 - t1
            a['first'] = min(a['first'], t0); a['last'] = max(a['last'], t2)
            a['chunks'] += 1; a['bytes'] += nb
        busy = [a['busy'] / 1e6 for a in th.values()]
        lasts = [a['last'] for a in th.values()]
        win = (hi - lo) / 1e6
        chunk_scan = [(x[5] - x[4]) / 1e6 for x in rows]
        chunk_csr = [(x[6] - x[5]) / 1e6 for x in rows]
        per.append({
            'window_ms': win, 'threads': len(th), 'chunks': len(rows),
            'busy_max_ms': max(busy), 'busy_min_ms': min(busy), 'busy_mean_ms': sum(busy) / len(busy),
            'busy_sum_ms': sum(busy), 'scan_sum_ms': sum(a['scan'] for a in th.values()) / 1e6,
            'csr_sum_ms': sum(a['csr'] for a in th.values()) / 1e6,
            'csr_frac_of_busy': sum(a['csr'] for a in th.values()) / max(1, sum(a['busy'] for a in th.values())),
            'utilization': sum(busy) / (len(th) * win),
            'spawn_delay_ms': (min(a['first'] for a in th.values()) - lo) / 1e6,
            'idle_tail_ms': (max(lasts) - min(lasts)) / 1e6,
            'join_delay_ms': (hi - max(lasts)) / 1e6,
            'chunk_scan_ms_median': med(chunk_scan), 'chunk_scan_ms_max': max(chunk_scan),
            'chunk_csr_ms_median': med(chunk_csr), 'chunk_csr_ms_max': max(chunk_csr),
            'scan_mb_per_s_per_thread': sum(x[3] for x in rows) / 1e6 / (sum(x[5] - x[4] for x in rows) / 1e9),
            'stream_cap_bytes_max': max(x[8] for x in rows) * 2,
            'stream_len_bytes_max': max(x[7] for x in rows) * 2,
            'stream_cap_bytes_sum': sum(x[8] for x in rows) * 2,
        })
        for t, a in th.items():
            by_thread.setdefault(t, []).append({'busy_ms': a['busy'] / 1e6, 'scan_ms': a['scan'] / 1e6,
                                                'csr_ms': a['csr'] / 1e6, 'chunks': a['chunks'],
                                                'end_ms_after_index_start': (a['last'] - lo) / 1e6})
    return {'index': med_dicts(per), 'index_by_thread': {str(t): med_dicts(v) for t, v in sorted(by_thread.items())}}


def sum_block(runs):
    per = []
    for r in runs:
        ts = phase_ts(r)
        lo, hi = ts['hits_collect'], ts['answer']
        th = {}
        for (t, b, nb, np_, t0, t1) in [x[:6] for x in r['parsed']['BLOCK']]:
            a = th.setdefault(t, {'busy': 0, 'first': t0, 'last': t1, 'blocks': 0})
            a['busy'] += t1 - t0; a['first'] = min(a['first'], t0); a['last'] = max(a['last'], t1); a['blocks'] += 1
        busy = [a['busy'] / 1e6 for a in th.values()]
        lasts = [a['last'] for a in th.values()]
        blk = [(x[5] - x[4]) / 1e3 for x in r['parsed']['BLOCK']]
        win = (hi - lo) / 1e6
        per.append({'window_ms': win, 'blocks': len(blk), 'busy_max_ms': max(busy), 'busy_min_ms': min(busy),
                    'busy_mean_ms': sum(busy) / len(busy), 'busy_sum_ms': sum(busy),
                    'utilization': sum(busy) / (len(th) * win),
                    'spawn_delay_ms': (min(a['first'] for a in th.values()) - lo) / 1e6,
                    'idle_tail_ms': (max(lasts) - min(lasts)) / 1e6, 'join_delay_ms': (hi - max(lasts)) / 1e6,
                    'block_us_median': med(blk), 'block_us_max': max(blk)})
    return {'answer': med_dicts(per)}


def sum_qthread(runs):
    per = []
    for r in runs:
        q = r['parsed']['QTHREAD']
        tot = [(x[1] + x[2]) / 1e6 for x in q]
        per.append({'bool_ms_sum': sum(x[1] for x in q) / 1e6, 'phrase_ms_sum': sum(x[2] for x in q) / 1e6,
                    'nbool': sum(x[3] for x in q), 'nphrase': sum(x[4] for x in q),
                    'query_ms_thread_max': max(tot), 'query_ms_thread_min': min(tot)})
    s = med_dicts(per)
    s['bool_frac'] = s['bool_ms_sum'] / (s['bool_ms_sum'] + s['phrase_ms_sum'])
    return {'answer_kinds': s}


def sum_qkind(runs):
    out = {}
    for name in [x[0] for x in runs[0]['parsed']['QKIND']]:
        rows = [[x for x in r['parsed']['QKIND'] if x[0] == name][0] for r in runs]
        out[name] = {'count': med(x[1] for x in rows), 'total_ms': med(x[2] / 1e6 for x in rows),
                     'mean_us': med(x[2] / 1e3 / max(1, x[1]) for x in rows), 'max_us': med(x[3] / 1e3 for x in rows),
                     'mean_clauses': med(x[4] / max(1, x[1]) for x in rows)}
    return {'qkind': out}


def sum_qslow(runs):
    seen = {}
    for r in runs:
        for qi, n, kind, ncl in [x[:4] for x in r['parsed']['QSLOW']]:
            seen.setdefault(qi, {'qi': qi, 'kind': kind, 'nclauses': ncl, 'ns': []})['ns'].append(n)
    rows = [{'qi': v['qi'], 'kind': v['kind'], 'nclauses': v['nclauses'], 'runs_in_top20': len(v['ns']),
             'median_us': med(v['ns']) / 1e3} for v in seen.values()]
    rows.sort(key=lambda x: (-x['runs_in_top20'], -x['median_us']))
    return {'qslow': rows[:20]}


def sum_info(runs):
    return {'info': {x[0]: x[1] for x in runs[-1]['parsed']['INFO']}}


def sum_memt(runs):
    per = []
    for r in runs:
        m = r['parsed']['MEMT']
        top = max(m, key=lambda x: x[1])
        per.append({'samples': len(m), 'max_vmrss_kb': top[1], 'max_vmrss_at_ms': top[0] / 1e6,
                    'max_rssanon_kb': max(x[2] for x in m), 'max_rssfile_kb': max(x[3] for x in m)})
    return {'memt': med_dicts(per)}


def sum_scan(runs):
    per, by_thread = [], {}
    for r in runs:
        cpn = r['parsed']['TSC'][0][0] if 'TSC' in r['parsed'] else None
        rows = r['parsed']['SCAN']
        tot = [sum(x[2 + i] for x in rows) for i in range(6)]
        allc = sum(tot)
        ntok, ndocs = sum(x[8] for x in rows), sum(x[11] for x in rows)
        x = {f'{p}_pct': 100 * v / allc for p, v in zip(SCAN_PARTS, tot)}
        x.update({f'{p}_cycles_per_token': v / ntok for p, v in zip(SCAN_PARTS, tot)})
        x.update({f'{p}_cycles_per_doc': v / ndocs for p, v in zip(SCAN_PARTS, tot)})
        if cpn:
            x.update({f'{p}_ms_sum': v / cpn / 1e6 for p, v in zip(SCAN_PARTS, tot)})
            x['parts_ms_sum'] = allc / cpn / 1e6
            x['total_ms_sum'] = sum(x_[17] for x_ in rows) / cpn / 1e6
            x['tsc_cycles_per_ns'] = cpn
        x['unattributed_pct_of_total'] = 100 * (1 - allc / sum(x_[17] for x_ in rows))
        x.update({'ntokens': ntok, 'ndocs': ndocs, 'nanchors_checked': sum(x_[9] for x_ in rows),
                  'nhits': sum(x_[10] for x_ in rows), 'n_list': sum(x_[12] for x_ in rows),
                  'n_bitmap': sum(x_[13] for x_ in rows), 'n_none': sum(x_[14] for x_ in rows),
                  'n_phrase_only': sum(x_[15] for x_ in rows), 'n_long': sum(x_[16] for x_ in rows),
                  'tokens_per_doc': ntok / ndocs})
        per.append(x)
        th = {}
        for row in rows:
            a = th.setdefault(row[0], [0] * 7)
            for i in range(6):
                a[i] += row[2 + i]
            a[6] += row[17]
        for t, a in th.items():
            d = {f'{p}_mcycles': v / 1e6 for p, v in zip(SCAN_PARTS, a)}
            d['total_mcycles'] = a[6] / 1e6
            by_thread.setdefault(t, []).append(d)
    return {'scan': med_dicts(per), 'scan_by_thread': {str(t): med_dicts(v) for t, v in sorted(by_thread.items())}}


SUMMARIZERS.update({
    'PHASE': sum_phase,
    'MEM': lambda runs: {'mem_kb': sum_mem(runs, 'MEM', ('VmHWM', 'VmRSS', 'RssAnon', 'RssFile'))},
    'SMAPS': lambda runs: {'smaps_kb': sum_mem(runs, 'SMAPS', ('Rss', 'Pss', 'Pss_Anon', 'Pss_File', 'Anonymous'))},
    'MEMT': sum_memt, 'INFO': sum_info, 'IDX': sum_idx, 'BLOCK': sum_block, 'QTHREAD': sum_qthread,
    'QKIND': sum_qkind, 'QSLOW': sum_qslow, 'SCAN': sum_scan,
})


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


def run_once(binary, data, out, threads, extra_env=None):
    res = pathlib.Path(out) / 'results.txt'
    if res.exists():
        res.unlink()
    env = {**os.environ, 'SD_DATA': data, 'SD_OUT': out}
    env.pop('SD_THREADS', None)
    env.update(extra_env or {})
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
    p.add_argument('--keep-parsed', action='store_true',
                   help="also save run['parsed'] (by default only the raw instr lines, which re-parse)")
    p.add_argument('--baseline', default=None,
                   help='uninstrumented binary run alternately with --binary (same settings) to measure overhead')
    p.add_argument('--env', action='append', default=[], help='KEY=VALUE for the child, e.g. SD_PROF_SMAPS=1')
    a = p.parse_args()
    extra = dict(e.split('=', 1) for e in a.env)
    assert a.warmup >= 1 and a.runs >= 1
    binary = os.path.abspath(a.binary)
    settings = [None] if a.threads is None else [int(t) for t in a.threads.split(',')]
    out = a.out or tempfile.mkdtemp(prefix='sd-b-linux-profile-', dir='/tmp')
    os.makedirs(out, exist_ok=True)
    base = os.path.abspath(a.baseline) if a.baseline else None
    rows, base_rows, summary = [], [], {}
    try:
        for t in settings:
            for run in range(-a.warmup, a.runs):
                for b, dest in ([(base, base_rows)] if base else []) + [(binary, rows)]:
                    r = run_once(b, a.data, out, t, extra if b == binary else None)
                    r['run'] = run; r['warmup'] = run < 0
                    if not a.keep_stdout:
                        r.pop('stdout')
                    dest.append(r)
                    print(f"{'base ' if b == base else ''}threads={t} run={run} wall={r['wall_s']:.3f}s "
                          f"cpu={r['cpu_s']:.3f}s maxrss={r['maxrss_kib']}KiB minflt={r['minflt']}", flush=True)
            key = 'default' if t is None else str(t)
            measured = [r for r in rows if r['threads'] == t and not r['warmup']]
            summary[key] = summarize(measured)
            if base:
                bm = [r for r in base_rows if r['threads'] == t and not r['warmup']]
                bs = summarize(bm)
                summary[key]['baseline'] = bs
                summary[key]['overhead'] = {
                    f'{m}_ratio': summary[key]['median_' + m] / bs['median_' + m]
                    for m in ('wall_s', 'cpu_s', 'maxrss_kib', 'minflt')}
    finally:
        if a.out is None:
            shutil.rmtree(out, ignore_errors=True)
    if not a.keep_parsed:
        for r in rows + base_rows:
            r.pop('parsed', None)
    report = {'environment': environment(binary, a.data), 'expected_sha256': EXPECTED,
              'warmup': a.warmup, 'child_env': extra, 'summary': summary, 'runs': rows}
    if base:
        report['baseline_binary_sha256'] = sha256_file(base)
        report['baseline_runs'] = base_rows
    pathlib.Path(a.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

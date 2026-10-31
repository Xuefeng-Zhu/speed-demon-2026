#!/usr/bin/env python3
"""Exercise forced scan, partial-abort fallback, fanout, and exact output order."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = (HERE / os.environ.get('B_SCAN_SOURCE', 'candidate.rs')).read_text()


def build(out, *, budget, sample_limit, threads, diagnostic=False):
    src = SRC.replace('const SCAN_BUDGET: u32 = 64;', f'const SCAN_BUDGET: u32 = {budget};')
    src = src.replace('const SAMPLE_ANCHOR_LIMIT: u64 = 2;', f'const SAMPLE_ANCHOR_LIMIT: u64 = {sample_limit};')
    old = 'let nthreads = thread::available_parallelism().map_or(4, |n| n.get()).min(12);'
    assert src.count(old) == 1
    src = src.replace(old, f'let nthreads = {threads};')
    if diagnostic:
        old = '    let cache = DenseCache::new(plan.keys.len(), 64 * 1024 * 1024);'
        assert src.count(old) == 1
        src = src.replace(old, '''    let mut diag_aborted = 0usize;
    let mut diag_mixed = 0usize;
    let mut diag_mixed_partial = 0usize;
    for q in 0..plan.scan_count {
        let n = parts.iter().filter(|p| p.scan_aborted[q]).count();
        if n > 0 { diag_aborted += 1; }
        if n > 0 && n < parts.len() {
            diag_mixed += 1;
            if parts.iter().any(|p| !p.scan_aborted[q] && p.scan_hits[q].count > 0) {
                diag_mixed_partial += 1;
            }
        }
    }
    eprintln!("SCAN_DIAG selected={} aborted={} mixed={} mixed_partial={}", plan.scan_count, diag_aborted, diag_mixed, diag_mixed_partial);
    let cache = DenseCache::new(plan.keys.len(), 64 * 1024 * 1024);''')
    source = out.with_suffix('.rs')
    source.write_text(src)
    subprocess.run(['rustc', '--edition=2021', '-O', '-C', 'overflow-checks=yes',
                    '-C', 'debug-assertions=yes', str(source), '-o', str(out)], check=True)


def run(binary, data, out):
    out.mkdir(exist_ok=True)
    p = subprocess.run([str(binary)], env={**os.environ, 'SD_DATA': str(data), 'SD_OUT': str(out)},
                       capture_output=True, check=True, timeout=120)
    return (out / 'results.txt').read_bytes(), p.stderr.decode()


def line(docs):
    return (str(len(docs)) + ' ' + str(sum(docs)) + ''.join(' ' + str(i) for i in docs[:10]) + '\n').encode()


with tempfile.TemporaryDirectory(prefix='b-scan-verify-') as td:
    td = Path(td)
    forced = td / 'forced'
    build(forced, budget='4294967295', sample_limit='18446744073709551615', threads=4)
    env = {**os.environ, 'B_RUST_BINARY': str(forced)}
    subprocess.run([sys.executable, str(ROOT / 'experiments/b-boolean-clauses/algebra.py'),
                    str(ROOT / 'experiments/b-rust-positional-adapter.py')], env=env, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / 'experiments/b-bounded-fuzz.py'),
                    str(ROOT / 'experiments/b-rust-positional-adapter.py')], env=env, cwd=ROOT, check=True, timeout=180)

    # A sampled prefix has no 'flood'. Later a sparse run precedes a dense run,
    # so one chunk completes a nonempty summary while another must abort after
    # accumulating results. Duplicate clauses and duplicate query lines exercise
    # deduplication both before and after the fallback decision.
    data = td / 'data'
    data.mkdir()
    flood = set(range(1200, 1210)) | set(range(1650, 2200))
    with (data / 'docs.txt').open('w') as f:
        for i in range(2200):
            text = ('flood flood keep' if i in flood else 'keep')
            f.write(f'{i}\t{text}' + ' ' * 440 + '\n')
    choices = [
        ('BOOL flood OR flood AND keep', sorted(flood)),
        ('BOOL flood NOT flood OR keep AND absent', []),
        ('BOOL flood OR absent NOT keep', []),
        ('BOOL keep NOT flood OR absent', [i for i in range(2200) if i not in flood]),
        ('PHRASE "flood flood"', sorted(flood)),
    ]
    queries = [choices[i % len(choices)] for i in range(10005)]
    (data / 'queries.txt').write_text(''.join(q + '\n' for q, _ in queries))
    expected = b''.join(line(ids) for _, ids in queries)
    candidate = td / 'budget64'
    build(candidate, budget=64, sample_limit=2, threads=4, diagnostic=True)
    actual, stderr = run(candidate, data, td / 'out')
    assert actual == expected, 'wrong result or order after fanout/abort'
    m = re.search(r'SCAN_DIAG selected=(\d+) aborted=(\d+) mixed=(\d+) mixed_partial=(\d+)', stderr)
    assert m, stderr
    selected, aborted, mixed, partial = map(int, m.groups())
    assert selected > 1000 and aborted > 1000 and mixed > 1000 and partial > 1000, m.groups()
    print('PASS sampled-anchor fanout, duplicate clauses and queries, mixed-chunk partial abort', m.groups())

    for budget in (0, 1, 3):
        candidate = td / f'budget{budget}'
        build(candidate, budget=budget, sample_limit='18446744073709551615', threads=4, diagnostic=True)
        actual, stderr = run(candidate, data, td / f'out{budget}')
        assert actual == expected, f'wrong output at budget {budget}'
        assert re.search(r'SCAN_DIAG selected=[1-9]\d* aborted=[1-9]', stderr), stderr
        print(f'PASS forced all-query selection at budget {budget}')

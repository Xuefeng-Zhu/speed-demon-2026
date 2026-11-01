#!/usr/bin/env python3
"""Candidate chunkings as text substitutions on baseline.rs.

    python3 mkcand.py baseline.rs outdir      writes outdir/<name>.rs for every candidate

Every candidate replaces only the chunk-count line and the first line of `cut` (and the
comment above them); the 64-document alignment, the claim loop and the sort stay.
"""
import pathlib, sys

OLD = '''    // Equal byte ranges, each moved to the next line whose id is a multiple
    // of 64; at most 65,536 lines per chunk.
'''
OLD2 = '''    let nchunks = nthreads * data.len().div_ceil(nthreads << 24).max(1);
    let cut = |k| {
        let mut i = line_start(data, k * data.len() / nchunks);
'''


def tail(b, s):
    """m rounds of nthreads equal ranges of weight b, then one round of nthreads of weight s."""
    return (f'''    // m rounds of nthreads equal byte ranges, then a round of nthreads ranges
    // {s}/{b} as large, which the threads that are done first take, so slow threads
    // end with small ranges. Each range is moved to the next line whose id is a
    // multiple of 64; at most 65,536 lines per chunk.
''', f'''    let m = data.len().div_ceil(nthreads << 24).max(1);
    let nchunks = nthreads * (m + 1);
    let cut = |k: usize| {{
        let w = {b} * k - {b - s} * k.saturating_sub(nthreads * m);
        let mut i = line_start(data, w * data.len() / (nthreads * ({b} * m + {s})));
''')


def hyb2(b, s):
    """max(m, 2) rounds: the last round's ranges have weight s, the others weight b."""
    return (f'''    // max(m, 2) rounds of nthreads byte ranges; the last round's ranges are
    // {s}/{b} as large as the others, and the threads that are done first take them,
    // so slow threads end with small ranges. Each range is moved to the next line
    // whose id is a multiple of 64; at most 65,536 lines per chunk.
''', f'''    let nchunks = nthreads * data.len().div_ceil(nthreads << 24).max(2);
    let cut = |k: usize| {{
        let w = {b} * k - {b - s} * k.saturating_sub(nchunks - nthreads);
        let mut i = line_start(data, w * data.len() / ({b} * nchunks - {b - s} * nthreads));
''')


def hyb(b, only1):
    """max(m, 2) rounds: the last round's ranges have weight 1, the others weight b
    (b only when m == 1 if only1, so 8 and 12 threads keep the baseline's chunks)."""
    bexpr = f'1 + {b - 1} * (m == 1) as usize' if only1 else str(b)
    return (f'''    // max(m, 2) rounds of nthreads byte ranges; the last round's ranges are
    // 1/{b} as large as the others{' when one round would do' if only1 else ''}, and the threads that
    // are done first take them, so slow threads end with small ranges. Each range
    // is moved to the next line whose id is a multiple of 64; at most 65,536 lines
    // per chunk.
''', f'''    let m = data.len().div_ceil(nthreads << 24).max(1);
    let (nchunks, b) = (nthreads * m.max(2), {bexpr});
    let cut = |k: usize| {{
        let w = b * k - (b - 1) * k.saturating_sub(nchunks - nthreads);
        let mut i = line_start(data, w * data.len() / (b * nchunks - (b - 1) * nthreads));
''')


CANDS = {
    # (a) one more round of equal ranges
    'eq1': ('''    // m + 1 rounds of nthreads equal byte ranges, each moved to the next line
    // whose id is a multiple of 64; at most 65,536 lines per chunk.
''', '''    let nchunks = nthreads * (data.len().div_ceil(nthreads << 24).max(1) + 1);
    let cut = |k| {
        let mut i = line_start(data, k * data.len() / nchunks);
'''),
    # (b) a final round of smaller ranges
    'tail2': tail(2, 1),
    'tail3': tail(3, 1),
    'tail4': tail(4, 1),
    'h31': hyb(3, False),
    'h21': hyb(2, False),
    'h41': hyb2(4, 1),
    'h52': hyb2(5, 2),
    'h31x': hyb(3, True),
    'h21x': hyb(2, True),
    # (c) sizes falling linearly over N(m + 1) ranges: cut at 1 - (1 - k/C)^2
    'pow2': ('''    // nchunks byte ranges whose sizes fall linearly, from twice the mean to
    // nearly zero; each is moved to the next line whose id is a multiple of 64.
''', '''    let nchunks = nthreads * (data.len().div_ceil(nthreads << 24).max(1) + 1);
    let cut = |k: usize| {
        let mut i = line_start(data, k * (2 * nchunks - k) * data.len() / (nchunks * nchunks));
'''),
}

if __name__ == '__main__':
    src = open(sys.argv[1]).read()
    assert src.count(OLD) == 1 and src.count(OLD2) == 1
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name, (c, code) in CANDS.items():
        (out / f'{name}.rs').write_text(src.replace(OLD, c).replace(OLD2, code))
        print(name)

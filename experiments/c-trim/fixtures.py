#!/usr/bin/env python3
"""fixtures.py BIN [--threads T ...]: byte-compares BIN (honouring SD_THREADS) with
official/reference/c_join.py on generated tiny/sample seed 42 and on hand-made fixtures:
long names (up to 70 KB, quoted with "" escapes), 15-100 KB records (long notes with quoted LFs),
a BOM on the header, a file whose last record has no line end, and many tiny records.
Default threads: 1 3 5 8 12 20."""
import argparse, os, random, shutil, subprocess, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'official', 'reference'))
import c_join  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('bin')
ap.add_argument('--threads', action='append', default=[])
a = ap.parse_args()
threads = a.threads or ['1', '3', '5', '8', '12', '20']


def q(s):
    return '"' + s.replace('"', '""') + '"'


def write(d, rows, regions, bom=False, last_eol=True):
    os.makedirs(d)
    with open(f'{d}/regions.csv', 'w') as f:
        f.write('region_id,country\n' + ''.join(f'{r},{c}\n' for r, c in regions))
    body = ('\ufeff' if bom else '') + 'id,name,note,region_id,amount\r\n' + '\r\n'.join(rows)
    with open(f'{d}/records.csv', 'wb') as f:
        f.write((body + ('\r\n' if last_eol else '')).encode())


def fixtures(root):
    rng = random.Random(5)
    regions = [(i, ''.join(rng.choice('ABCDEFG') for _ in range(3))) for i in range(1, 400, 3)]
    names = ['a', 'b c', 'Q"x"', 'x' * 70000, 'y' * 15000 + '"' + 'z' * 100, 'short', 'with, comma']

    def rec(i, name, note):
        reg = rng.choice([r for r, _ in regions] + [0, 2, 9999999])
        amt = rng.randint(-99999, 99999)
        nm = q(name) if rng.random() < .8 or '"' in name or ',' in name else name
        sign = '-' if amt < 0 else ''
        return f'{i},{nm},{q(note)},{reg},{sign}{abs(amt) // 100}.{abs(amt) % 100:02d}'

    big = [rec(i, rng.choice(names), ('n\n' * rng.randint(5000, 50000))[:rng.randint(15000, 100000)])
           for i in range(1, 60)]
    write(f'{root}/big', big, regions)
    write(f'{root}/big-unterminated', big, regions, last_eol=False)
    small = [rec(i, rng.choice(names[:3] + names[5:]) + str(rng.randint(0, 3000)), 'n' * rng.randint(0, 40))
             for i in range(1, 40000)]
    write(f'{root}/many-bom', small, regions, bom=True)
    write(f'{root}/many-unterminated', small, regions, last_eol=False)
    gen = os.path.join(ROOT, 'official', 'generators', 'c_join.py')
    for sc in ('tiny', 'sample'):
        subprocess.run([sys.executable, gen, '--seed', '42', '--scale', sc, '--out', f'{root}/{sc}-s42'], check=True,
                       stdout=subprocess.DEVNULL)
    return ['big', 'big-unterminated', 'many-bom', 'many-unterminated', 'tiny-s42', 'sample-s42']


bad = 0
with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
    for name in fixtures(root):
        d = f'{root}/{name}'
        ref = f'{d}-ref'
        os.makedirs(ref)
        c_join.main(d, ref)
        want = open(f'{ref}/aggregates.txt', 'rb').read()
        for t in threads:
            out = tempfile.mkdtemp(dir='/dev/shm')
            subprocess.run([a.bin], env=dict(os.environ, SD_DATA=d, SD_OUT=out, SD_THREADS=t), check=True)
            ok = open(f'{out}/aggregates.txt', 'rb').read() == want
            shutil.rmtree(out)
            bad += not ok
            print(f'{name:18} t={t:>2} {"ok" if ok else "MISMATCH"}')
print('FAIL' if bad else 'all ok')
sys.exit(1 if bad else 0)

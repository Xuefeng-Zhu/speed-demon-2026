#!/usr/bin/env python3
"""Exercise full u16 local-ID range and multichunk absolute IDs against set algebra."""
import argparse
import os
from pathlib import Path
import random
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('binary', type=Path)
a = p.parse_args()
binary = str(a.binary.resolve(strict=True))
with tempfile.TemporaryDirectory(prefix='b-opt8-query-boundary-') as tmp:
    root = Path(tmp)
    for n, threads in [(65536, 1), (250000, 8), (250000, 12)]:
        data, out = root / f'data-{n}-{threads}', root / f'out-{n}-{threads}'
        data.mkdir()
        out.mkdir()
        boundary = {0,1,62,63,64,65,127,128,1023,1024,32767,32768,65534,65535,65536,131071,131072,n-2,n-1}
        sets = {
            'a': {d for d in boundary if d < n},
            'b': {d for d in boundary if d < n and d % 3 == 0},
            'medium': set(range(0,n,256)),
            'near': set(range(1,n,257)),
            'even': set(range(0,n,2)),
            'last': {n-1},
            'missing': set(),
        }
        with (data/'docs.txt').open('w') as f:
            for i in range(n):
                f.write(f'{i}\t'+' '.join(t for t,s in sets.items() if i in s)+'\n')
        queries = [[('OR',t)] for t in sets]
        # Both binary-search directions, list merge and bitmap/list transitions.
        queries += [[('OR',x),(op,y)] for x in sets for y in sets for op in ['OR','AND','NOT']]
        r = random.Random(268)
        queries += [[('OR',r.choice(list(sets)))]+[(r.choice(['OR','AND','NOT']),r.choice(list(sets))) for _ in range(r.randrange(1,6))] for _ in range(400)]
        (data/'queries.txt').write_text(''.join('BOOL '+q[0][1]+''.join(f' {op} {t}' for op,t in q[1:])+'\n' for q in queries))
        expected=[]
        for q in queries:
            ids=set()
            for op,t in q:
                if op=='OR': ids |= sets[t]
                elif op=='AND': ids &= sets[t]
                else: ids -= sets[t]
            ordered=sorted(ids)
            expected.append(f'{len(ids)} {sum(ids)}'+''.join(f' {i}' for i in ordered[:10])+'\n')
        subprocess.run([binary], env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out),'SD_THREADS':str(threads)}, check=True,timeout=60)
        actual=(out/'results.txt').read_text()
        assert actual==''.join(expected), (n,threads)
        print(f'PASS n={n} threads={threads}, {len(queries)} Boolean expressions')

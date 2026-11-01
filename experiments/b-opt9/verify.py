#!/usr/bin/env python3
"""Differential test isolated candidates against the organizer's reference."""
import argparse, importlib.util, json, os, random, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('reference', ROOT/'official/reference/b_index.py')
ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('binaries', nargs='+')
binaries = p.parse_args().binaries
passes = 0
with tempfile.TemporaryDirectory(prefix='b-opt8-memory-verify-') as td:
    d = Path(td); out = d/'out'; out.mkdir()
    for seed in range(20):
        rng = random.Random(90700 + seed)
        vocab = ['alpha','beta','gamma','delta','once','absent','x','z'*16,'longtoken1234567890123456789012345']
        vocab += ['v'+str(i) for i in range(35)]
        n = [1,10,63,64,65,127,128,129,1023,1024][seed%10]
        docs = []
        for i in range(n):
            toks = [rng.choice(vocab[:-1]) for _ in range(rng.randrange(0,40))]
            if i%19 == 0: toks += ['alpha','beta','alpha','beta']
            if i%7 == 0: toks = [t.upper() for t in toks]
            docs.append(str(i).encode()+b'\t'+b'\xc3\xa9!'.join(t.encode() for t in toks)+b'\n')
        (d/'docs.txt').write_bytes(b''.join(docs))
        queries = ['BOOL alpha', 'BOOL absent', 'PHRASE alpha beta']
        for _ in range(200):
            if rng.randrange(3):
                q = 'BOOL '+rng.choice(vocab)
                for _ in range(rng.randrange(0,5)):
                    q += ' '+rng.choice(['AND','OR','NOT'])+' '+rng.choice(vocab)
            else:
                q = 'PHRASE '+' '.join(rng.choices(vocab,k=rng.randrange(2,9)))
            queries.append(q)
        (d/'queries.txt').write_text('\n'.join(queries)+'\n')
        texts, index = ref.load_corpus(str(d/'docs.txt'))
        expected = []
        for query in queries:
            kind, *terms = query.encode().split()
            ids = ref.run_bool(index,terms) if kind==b'BOOL' else ref.run_phrase(index,texts,terms)
            expected.append(ref.format_result(ids)+'\n')
        want = ''.join(expected).encode()
        for binary in binaries:
            for threads in [1,2,7,12]:
                p = subprocess.run([binary],env=dict(os.environ,SD_DATA=str(d),SD_OUT=str(out),SD_THREADS=str(threads)),capture_output=True)
                assert p.returncode == 0, (seed,binary,threads,p.stderr.decode())
                got = (out/'results.txt').read_bytes()
                assert got == want, (seed,binary,threads,got[:100],want[:100])
                passes += 1
print(json.dumps({'reference_comparisons':passes,'seeds':20,'thread_counts':[1,2,7,12]}))

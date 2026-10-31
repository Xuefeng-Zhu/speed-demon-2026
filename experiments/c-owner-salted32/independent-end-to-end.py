from pathlib import Path
import os, subprocess, sys, tempfile
root = Path(__file__).resolve().parents[2]
source = (Path(__file__).parent/'candidate.rs').read_text()
old = 'let n = thread::available_parallelism().map_or(1, |n| n.get());'
assert source.count(old) == 1
source = source.replace(old, 'let n = std::env::var("SD_TEST_WORKERS").unwrap().parse::<usize>().unwrap();')
with tempfile.TemporaryDirectory(prefix='c-low32-review-') as d:
    p=Path(d); (p/'data').mkdir(); (p/'ref').mkdir(); (p/'out').mkdir()
    (p/'source.rs').write_text(source)
    subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes'] + (['-C','target-cpu=x86-64-v3'] if '--avx2' in sys.argv else []) + [str(p/'source.rs'),'-o',str(p/'candidate')],check=True,timeout=90)
    (p/'data'/'regions.csv').write_bytes(b'region_id,country\n1,AAA\n2,BBB\n')
    names=['DQIVBOMJJX','UVUOJQWQQU']
    rows=['\ufeffid,name,note,region_id,amount\r\n']
    for i in range(1,12001):
        name=names[(i//3)%2]; group=1+(i%3); note='"hello\nworld"' if i%41==0 else '"hello"'
        bom='\ufeff' if i%97==0 else ''
        rows.append(f'{bom}{i},"{name}",{note},{group},{i%17}.42\r\n')
    (p/'data'/'records.csv').write_bytes(''.join(rows).encode())
    subprocess.run(['python3',str(root/'official/reference/c_join.py'),'--data',str(p/'data'),'--out',str(p/'ref')],check=True,timeout=90)
    expected=(p/'ref'/'aggregates.txt').read_bytes()
    for workers in [1,2,7,12,32]:
        env={**os.environ,'SD_DATA':str(p/'data'),'SD_OUT':str(p/'out'),'SD_TEST_WORKERS':str(workers)}
        subprocess.run([str(p/'candidate')],env=env,check=True,timeout=90)
        assert (p/'out'/'aggregates.txt').read_bytes()==expected, workers
    print('PASS official Python reference, 12000 records, two real equal-low32 names, workers 1/2/7/12/32')

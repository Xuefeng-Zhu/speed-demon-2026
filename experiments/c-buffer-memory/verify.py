#!/usr/bin/env python3
"""Exact current-C CSV oracle checks; run compiled x86 binaries on native Linux.

Process affinity controls available_parallelism without editing the tested sources.
No VM connection, daemon, allocator setting or persistent affinity is changed.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile

P=Path(__file__).resolve().parent
REPO=P.parents[1]
spec=importlib.util.spec_from_file_location('reference',REPO/'official/reference/c_join.py')
ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
HEADER=b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'
REGIONS=b'region_id,country\n1,AAA\n2,BBB\n9,AAA\n999999,ZZZ\n'


def quoted(s):return '"'+s.replace('"','""')+'"'


def row(i,name,note,rid=1,amount='0.00',bom=False,terminator=b'\r\n',empty_quoted=True):
    name=quoted(name) if name or empty_quoted else ''
    note=quoted(note) if note or empty_quoted else ''
    return (b'\xef\xbb\xbf' if bom else b'')+f'{i},{name},{note},{rid},{amount}'.encode()+terminator


def fixtures():
    yield 'minimal-empty-fields', HEADER+row(1,'','',empty_quoted=False)+row(2,'','')
    names=['A, B','Ann "Annie" Lee','Betts','Betts ','Betts  ','','Zoë','李明']
    notes=['','a,b','first\nsecond','"quoted"\nnext','embedded\n\nLF','\ufeffdata']
    blob=HEADER+b''.join(row(i+1,names[i%len(names)],notes[i%len(notes)],rid=[1,2,9,6,5000000][i%5],amount=['-999.99','99999.99','-0.01','0.00','1.25'][i%5],bom=i%4==0,terminator=b'\n' if i%3 else b'\r\n',empty_quoted=i%2==0) for i in range(80))
    yield 'quotes-BOM-multiline-mixed-terminators',blob
    yield 'numeric-widths',HEADER+row(39999999,'Name','N',999999,'99999.99')+row(1,'Other','N',9999999,'-999.99')
    sizes=[15,64,127,32703,32704,32705,32735,32736,32767,32768,65503,65504,65535,65536,100000]
    for n in sizes:
        note='x'*max(0,n//2-3)+'"\n,'+'y'*max(0,n-n//2-3)
        name='Name "Q"  '
        yield f'long-record-{n}',HEADER+row(1,name,note,bom=True)+row(2,'Tail','done',2,'-0.05')
    yield 'long-name-refills',HEADER+row(1,'A'*70000+' "Q"  ','short')+row(2,'A'*70000+' "Q"  ','other')
    yield 'unterminated-last-record',HEADER+row(1,'A, B','a\nb')+row(2,'Last "Q"','tail\nfield',5000000,'-0.01',bom=True,terminator=b'')
    yield 'concentrated-owner-event-blocks',HEADER+b''.join(row(i+1,'Same Name','n',rid=1 if i%2 else 2,amount='1.25') for i in range(20000))
    for seed in range(12):
        rng=random.Random(64000+seed)
        records=[]
        for i in range(180):
            name=rng.choice(names+['N'*rng.choice([1,63,64,65,4095])])
            note=rng.choice(notes+['z'*rng.choice([1,63,64,65,1009])])
            records.append(row(i+1,name,note,rng.choice([1,2,9,6,5000000]),rng.choice(['0.00','-0.05','-999.99','99999.99','1.25']),bom=rng.randrange(9)==0,terminator=rng.choice([b'\n',b'\r\n']),empty_quoted=bool(rng.randrange(2))))
        yield f'random-{seed}',HEADER+b''.join(records)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('binaries',nargs='+',type=Path)
    p.add_argument('--workers',default='1,2,7,12')
    p.add_argument('--report',type=Path)
    a=p.parse_args();bins=[str(v.resolve(strict=True)) for v in a.binaries]
    workers=[int(v) for v in a.workers.split(',')]
    if not hasattr(os,'sched_getaffinity'):p.error('native Linux affinity APIs are required')
    allowed=sorted(os.sched_getaffinity(0))
    if max(workers)>len(allowed):p.error(f'{len(allowed)} CPUs available; requested {max(workers)}')
    results=[]
    with tempfile.TemporaryDirectory(prefix='c-vm-exact-') as tmp:
        root=Path(tmp);data=root/'data';data.mkdir();oracle=root/'oracle';out=root/'out'
        (data/'regions.csv').write_bytes(REGIONS)
        for name,blob in fixtures():
            (data/'records.csv').write_bytes(blob)
            ref.main(str(data),str(oracle));expected=(oracle/'aggregates.txt').read_bytes()
            for binary in bins:
                for n in workers:
                    cpus=set(allowed[:n])
                    proc=subprocess.run([binary],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out)},preexec_fn=lambda:os.sched_setaffinity(0,cpus),capture_output=True,timeout=60)
                    assert proc.returncode==0,(name,binary,n,proc.stderr.decode(errors='replace'))
                    got=(out/'aggregates.txt').read_bytes()
                    assert got==expected,(name,binary,n,got[:120],expected[:120])
                    diag=[json.loads(line.removeprefix('C_WORKER ')) for line in proc.stderr.decode().splitlines() if line.startswith('C_WORKER ')]
                    if diag:
                        last=max(r['bits'] for r in diag)
                        assert len([r for r in diag if r['bits']==last])==n,(name,binary,n,'observed-worker-count')
                    results.append({'case':name,'binary':binary,'workers':n,'records_bytes':len(blob)})
    report={'reference_comparisons':len(results),'cases':len(set(r['case'] for r in results)),'worker_counts':workers,'rows':results}
    if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))


if __name__=='__main__':main()

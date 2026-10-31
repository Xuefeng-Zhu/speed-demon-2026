#!/usr/bin/env python3
"""Instrumented local correctness checks only; no benchmark and no production changes."""
import datetime, os, pathlib, random, subprocess, sys, tempfile
P = pathlib.Path(__file__).resolve().parent
S = P / 'candidate.rs'
with tempfile.TemporaryDirectory(prefix='a-crc-bound-') as tmp:
    t=pathlib.Path(tmp)
    bins={}
    sources={'base':(P/'baseline.rs').read_text()}
    raw=S.read_text()
    for cap in (0,1,48):
        for mode in ('sim','constant'):
            src=raw.replace('if probes > 48 { return None; }',f'if probes > {cap} {{ eprintln!("A_RESTART"); return None; }}')
            src=src.replace('    Some(c)\n}', '    eprintln!("A_FAST_OK");\n    Some(c)\n}')
            sources[f'{mode}{cap}']=src
    for name,src in sources.items():
        if sys.platform == 'darwin':
            src=src.replace('(1, 2, 0x10, 0x20, std::ptr::null_mut())','(1, 2, 0x10, 0x1000, std::ptr::null_mut())')
        path=t/(name+'.rs'); path.write_text(src)
        cmd=['rustc',str(path),'--edition=2021','-C','opt-level=3','-C','overflow-checks=no','-o',str(t/name)]
        if name.startswith('sim'): cmd += ['--cfg','sd_crc_sim']
        if name.startswith('constant'): cmd += ['--cfg','sd_crc_constant']
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        bins[name]=t/name
    for name in ('base','sim48','constant48'):
        subprocess.run(['python3',str(P.parent.parent/'track-a-verification/test.py'),'--binary',str(bins[name]),'--io','directories'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print('independent oracle passed',name,flush=True)
    for name in ('sim48','constant48'):
        subprocess.run(['python3',str(P.parent.parent/'track-a-verification/page_end_test.py'),'--binary',str(bins[name]),'--reference',str(P.parent.parent/'official/reference/a_ingest.py')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print('page-end reference passed',name,flush=True)
    data=t/'data'; data.mkdir(); (data/'requests.log').write_text('')
    rng=random.Random(996)
    # The first part has >2,048 colliding names and extreme latencies, while the
    # latter repeats a single endpoint, ensuring both restart and success modes.
    names=['/common-prefix-'+'x'*160+f'-{i:05d}' for i in range(2400)]
    with (data/'requests.log').open('w') as f:
        for i in range(14000):
            dt=datetime.datetime(2026,10,30,18)+datetime.timedelta(hours=i%72)
            name=names[i%len(names)] if i < 7000 else names[0]
            status=(200,500,599)[i%3]
            latency=(0, 1048574, 1048575, 4294967295, rng.randrange(100000))[i%5]
            f.write(dt.strftime('%Y-%m-%dT%H:%M:%S.000000Z')+f' GET {name} {status} {latency}\n')
    outputs={}
    for threads in (1,2,7,12,32):
        for name,binary in bins.items():
            out=t/'out'; out.mkdir(exist_ok=True)
            env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out),SD_THREADS=str(threads))
            p=subprocess.run([str(binary)],env=env,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            got=(out/'summary.txt').read_bytes(); (out/'summary.txt').unlink()
            if name=='base': outputs[threads]=got
            else: assert got==outputs[threads], (threads,name)
            if name.startswith('constant') and threads>1:
                assert b'A_RESTART' in p.stderr and b'A_FAST_OK' in p.stderr, (threads,name,p.stderr)
        print('mixed-shard and long-name/escape differential passed threads=',threads,flush=True)
print('PASS')

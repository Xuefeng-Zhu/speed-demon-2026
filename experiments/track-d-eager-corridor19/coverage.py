#!/usr/bin/env python3
from pathlib import Path
import os,subprocess,tempfile
src=(Path(__file__).parent/'candidate.rs').read_text()
marker='''            let (to,w)=next.unwrap(); let nd=d+w;'''
assert src.count(marker)==1
src=src.replace(marker,'''            EAGER.fetch_add(1, Relaxed);
'''+marker)
src=src.replace('const NONE: u64 = u64::MAX;','const NONE: u64 = u64::MAX; static EAGER: AtomicU64 = AtomicU64::new(0);')
needle='''    fs::write(format!("{out}/distances.txt"), text).unwrap();'''
assert src.count(needle)==1
src=src.replace(needle,needle+'''\n    eprintln!("eager={}",EAGER.load(Relaxed));''')
with tempfile.TemporaryDirectory(prefix='corridor19-coverage-') as tmp:
 p=Path(tmp); f=p/'candidate.rs'; b=p/'candidate'; f.write_text(src)
 subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-C','debug-assertions=yes',str(f),'-o',str(b)],check=True)
 data=p/'data';out=p/'out';data.mkdir();out.mkdir();n=120
 edges=[(u,u+1,1) for u in range(n-1)]+[(u+1,u,1) for u in range(n-1)]
 (data/'graph.txt').write_text(f'{n} {len(edges)}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges))
 (data/'queries.txt').write_text('0 119\n119 0\n0 0\n')
 r=subprocess.run([str(b)],check=True,capture_output=True,text=True,env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)))
 assert (out/'distances.txt').read_text()=='119\n119\n0\n'
 n=int(r.stderr.strip().split('=')[-1]);assert n>32,(n,r.stderr)
 print('PASS instrumented long-corridor propagation, correct answers, eager steps:',n)

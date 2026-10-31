import os, subprocess, tempfile, time, hashlib, sys
from pathlib import Path
with tempfile.TemporaryDirectory(prefix='b-duplicate-250k-') as temp:
 p=Path(temp); n=250000; phrase_n=19000; bool_n=31000
 with (p/'docs.txt').open('w') as f:
  for i in range(n):f.write(f'{i}\ta a\n')
 (p/'queries.txt').write_text('PHRASE "a a"\n'*phrase_n + 'BOOL z\n'*bool_n)
 out=p/'results.txt'; t=time.perf_counter()
 proc=subprocess.Popen([sys.argv[1],str(p/'docs.txt'),str(p/'queries.txt'),str(out)])
 _,st,ru=os.wait4(proc.pid,0);proc.returncode=os.waitstatus_to_exitcode(st); assert proc.returncode==0
 expected=(f'{n} {n*(n-1)//2} '+' '.join(map(str,range(10)))+'\n').encode()*phrase_n+b'0 0\n'*bool_n
 actual=out.read_bytes();assert actual==expected
 print('PASS full-count duplicate stress: 250000 docs, 19000 identical phrase queries, 31000 boolean queries; seconds',round(time.perf_counter()-t,3),'ru_maxrss_native',ru.ru_maxrss,'SHA256',hashlib.sha256(actual).hexdigest())

import subprocess,tempfile,sys
from pathlib import Path
matches={8,10,19,24,34,35,50,67,68,79,80,95}
with tempfile.TemporaryDirectory(prefix='b-shard-top10-') as d:
 p=Path(d);data=p/'data';ref=p/'ref';out=p/'out'
 for v in (data,ref,out):v.mkdir()
 with (data/'docs.txt').open('w') as f:
  for i in range(100):f.write(f'{i}\t'+('a a a b a a' if i in matches else 'a separator a')+'\n')
 (data/'queries.txt').write_text(('PHRASE "a a"\n'*200)+'PHRASE "a a a"\nPHRASE "a b a"\nPHRASE "a separator a"\nBOOL a NOT b\n')
 subprocess.run([sys.executable,'official/reference/b_index.py','--data',str(data),'--out',str(ref)],check=True)
 subprocess.run([sys.argv[1],str(data/'docs.txt'),str(data/'queries.txt'),str(out/'results.txt')],check=True)
 got=(out/'results.txt').read_bytes();expected=(ref/'results.txt').read_bytes();assert got==expected
 print('PASS distributed top-10, duplicate phrases and overlapping occurrences')

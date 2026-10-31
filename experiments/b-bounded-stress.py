import argparse,hashlib,pathlib,subprocess,sys,tempfile,resource,time
parser=argparse.ArgumentParser()
parser.add_argument("candidate", help="path to compiled candidate")
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='b-bounded-stress-') as td:
 root=pathlib.Path(td); d=root/'data';ref=root/'ref'; d.mkdir();ref.mkdir()
 def write(n):
  with (d/'docs.txt').open('w') as f:
   for i in range(n): f.write(f'{i}\ta a a a a a a a\n')
  (d/'queries.txt').write_text(('PHRASE "a a"\n'*19000)+'PHRASE "a a a a a a a a"\nPHRASE "a a a a a a a b"\nBOOL a\n')
 def expected(n):
  first=''.join(' '+str(i) for i in range(min(10,n)))
  allrow=f'{n} {n*(n-1)//2}{first}\n'
  return (allrow*19000+allrow+'0 0\n'+allrow).encode()
 write(100)
 subprocess.run([sys.executable,'official/reference/b_index.py','--data',str(d),'--out',str(ref)],check=True)
 subprocess.run([args.candidate,str(d/'docs.txt'),str(d/'queries.txt'),str(root/'out')],check=True)
 assert (root/'out').read_bytes()==(ref/'results.txt').read_bytes()==expected(100)
 print('PASS 100 documents; 19,000 duplicate phrases against official reference',flush=True)
 write(250000)
 started=time.monotonic()
 subprocess.run([args.candidate,str(d/'docs.txt'),str(d/'queries.txt'),str(root/'out')],check=True)
 assert (root/'out').read_bytes()==expected(250000)
 print('PASS 250,000 documents; 19,000 identical high-frequency phrases; seconds',round(time.monotonic()-started,3),'peak-child-RSS-bytes',resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * (1 if sys.platform == 'darwin' else 1024),'SHA-256',hashlib.sha256((root/'out').read_bytes()).hexdigest(),flush=True)

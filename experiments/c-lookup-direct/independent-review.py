from pathlib import Path
import itertools,os,random,subprocess,sys,tempfile
root=Path(__file__).resolve().parents[2]
needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
keys=[''.join(x) for x in itertools.product('ABCDEFGHIJKLMNOPQRSTUVWXYZ', repeat=3)]
indices=[(ord(k[0])-65)*676+(ord(k[1])-65)*26+ord(k[2])-65 for k in keys]
assert indices==list(range(17576))
print('PASS 17,576 direct country indices form a bijection',flush=True)
with tempfile.TemporaryDirectory(prefix='c-lookup-adversarial-') as td:
 p=Path(td);bins={};workers=(1,2,7,32)
 for source in ('baseline','combined'):
  raw=(root/f'experiments/c-lookup-direct/{source}.rs').read_text();assert raw.count(needle)==1
  for n in workers:
   src=p/f'{source}-{n}.rs';exe=p/f'{source}-{n}'
   src.write_text(raw.replace(needle,f'let n = {n};'))
   subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True)
   bins[(source,n)]=exe
 for case in range(4):
  d=p/f'case{case}';data=d/'data';ref=d/'ref';data.mkdir(parents=True);ref.mkdir()
  if case==0: rows=[]
  elif case==1: rows=[(1,'ZZZ')]
  elif case==2: rows=[(1,'ZZZ'),(3,'ABA'),(500,'AAA'),(1044,'AAA'),(999_999,'ABA')]
  else: rows=[(i+1,k) for i,k in enumerate(reversed(keys))]
  (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i},{code}\n' for i,code in rows))
  if case==3:
   ids=list(range(1,17577))+[9999999]
  elif case==2:ids=[1,2,3,4,500,1044,999998,999999,9999999,500,1044]
  else: ids=[1,2,999999,9999999,1]
  names=['""','', '"Bob"','"Bob "','"a, b"','"Ann ""A"""']
  body=[b'\xef\xbb\xbfid,name,note,region_id,amount\r\n']
  for i,rid in enumerate(ids):
   prefix=b'\xef\xbb\xbf' if i and i%13==0 else b''
   end=b'\r\n' if i==len(ids)-1 or i%2==0 else b'\n'
   row=f'{i+1},{names[i%len(names)]},"hello\nworld",{rid},{["0.00","-0.01","99999.99"][i%3]}'.encode()
   body.append(prefix+row+end)
  (data/'records.csv').write_bytes(b''.join(body))
  subprocess.run([sys.executable,str(root/'official/reference/c_join.py'),'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
  expected=(ref/'aggregates.txt').read_bytes()
  for source in ('baseline','combined'):
   for n in workers:
    out=d/f'out-{source}-{n}';out.mkdir()
    subprocess.run([str(bins[(source,n)])],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True,timeout=30)
    actual=(out/'aggregates.txt').read_bytes()
    if actual!=expected:raise SystemExit(f'FAIL {case=} {source=} {n=}')
  print(f'PASS case {case}: {len(rows)} region rows, {len(ids)} records, all implementations and worker counts',flush=True)
print('PASS 32 byte-exact reference executions',flush=True)

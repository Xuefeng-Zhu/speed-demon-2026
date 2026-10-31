import itertools,os,subprocess,sys,tempfile,pathlib,hashlib
W=4294967295; N=4096*3; edges=[]; qs=[]; answers=[]; pairs=[(i,j) for i in range(3) for j in range(3) if i!=j]
for case,code in enumerate(itertools.product((None,0,1,W),repeat=6)):
 base=case*3; ds=[[10**30]*3 for _ in range(3)]
 for i in range(3):ds[i][i]=0
 for (u,v),w in zip(pairs,code):
  if w is not None:edges.append(f'{base+u} {base+v} {w}\n');ds[u][v]=w
 for k in range(3):
  for i in range(3):
   for j in range(3):ds[i][j]=min(ds[i][j],ds[i][k]+ds[k][j])
 for i in range(3):
  for j in range(3):qs.append(f'{base+i} {base+j}\n');answers.append(f'{ds[i][j] if ds[i][j]<10**30 else -1}\n')
expected=''.join(answers).encode()
with tempfile.TemporaryDirectory(prefix='balanced-exhaustive-') as tmp:
 root=pathlib.Path(tmp);data=root/'data';data.mkdir(); (data/'graph.txt').write_text(f'{N} {len(edges)}\n'+''.join(edges));(data/'queries.txt').write_text(''.join(qs))
 for i,b in enumerate(sys.argv[1:]):
  out=root/str(i);out.mkdir();subprocess.run([b],check=True,env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out))); actual=(out/'distances.txt').read_bytes()
  if actual!=expected:raise SystemExit(f'FAIL {b}')
 print('PASS 4096 directed graphs / 36864 all-pairs queries each; SHA256',hashlib.sha256(expected).hexdigest())

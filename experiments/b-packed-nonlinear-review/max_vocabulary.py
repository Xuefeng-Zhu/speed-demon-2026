import argparse, hashlib, pathlib, random, subprocess, tempfile
parser = argparse.ArgumentParser(description='Compare Track B binaries against the reference on a maximum query-vocabulary fixture')
parser.add_argument('binaries', nargs='+', type=pathlib.Path)
args = parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
rng=random.Random(711491)
with tempfile.TemporaryDirectory(prefix='b-max-vocab-') as t:
 p=pathlib.Path(t); data=p/'data';ref=p/'ref';actual=p/'actual';data.mkdir();ref.mkdir();actual.mkdir()
 def term(i):
  s=f'w{i:08x}'
  return s+'z'*(i%24)
 qs=[]
 for i in range(31000):
  words=[term(6*i+j) for j in range(6)]
  qs.append('BOOL '+words[0]+''.join(' '+('AND','OR','NOT')[(i+j)%3]+' '+w for j,w in enumerate(words[1:])))
 for i in range(19000):
  qs.append('PHRASE "'+' '.join(term(186000+8*i+j) for j in range(8))+'"')
 assert len(qs)==50000
 (data/'queries.txt').write_text('\n'.join(qs)+'\n',encoding='ascii')
 with (data/'docs.txt').open('w',encoding='utf8') as f:
  for i in range(600):
   w=[term(rng.randrange(186000)) for _ in range(25)]
   if i<100: w += [term(186000+8*i+j) for j in range(8)]*2
   if i%4==0:w=[x.upper() for x in w]
   f.write(f'{i}\t'+'—'.join(w)+'\n')
 subprocess.run(['python3',str(root/'official/reference/b_index.py'),'--data',str(data),'--out',str(ref)],check=True)
 expected=(ref/'results.txt').read_bytes()
 for i, executable in enumerate(args.binaries):
  output=actual/(str(i)+'.txt')
  subprocess.run([str(executable.resolve()),str(data/'docs.txt'),str(data/'queries.txt'),str(output)],check=True)
  assert output.read_bytes()==expected,executable
 print('PASS 338000 distinct terms in 50000 queries (31000 six-term BOOL, 19000 eight-term PHRASE), 600 docs, Unicode separators and uppercase; '+str(len(args.binaries))+' binaries matched official reference, sha256='+hashlib.sha256(expected).hexdigest(),flush=True)

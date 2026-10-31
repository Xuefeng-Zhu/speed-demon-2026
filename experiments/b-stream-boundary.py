from pathlib import Path
import tempfile, subprocess, sys
root=Path(__file__).resolve().parent.parent
exe='/tmp/b-stream-boundary-review'
subprocess.run(['c++','-O3','-std=c++17','-pthread',str(root/'track-b/main.cpp'),'-o',exe],check=True)
with tempfile.TemporaryDirectory() as td:
 p=Path(td); data=p/'data';ref=p/'ref';out=p/'out'
 for d in (data,ref,out):d.mkdir()
 docs=[]
 for i in range(12):
  if i%2==0:
   prefix=(f'{i}\t'+'a ' * 524278).encode()
   docs.append(prefix+b' '*(1048575-len(prefix))+b'X'*32+b' Alpha beta'+b'\n')
  else: docs.append(f'{i}\tA x alpha beta x x\n'.encode())
 (data/'docs.txt').write_bytes(b''.join(docs))
 (data/'queries.txt').write_text('BOOL a\nBOOL x\nPHRASE "alpha beta"\nPHRASE "x x"\nBOOL '+('x'*32)+'\nBOOL x OR a NOT beta\n')
 subprocess.run([sys.executable,str(root/'official/reference/b_index.py'),'--data',str(data),'--out',str(ref)],check=True)
 subprocess.run([exe,str(data/'docs.txt'),str(data/'queries.txt'),str(out/'results.txt')],check=True)
 assert (ref/'results.txt').read_bytes()==(out/'results.txt').read_bytes()
 print('PASS six >1 MiB documents with 32-byte tokens across read boundaries and mixed shard documents')

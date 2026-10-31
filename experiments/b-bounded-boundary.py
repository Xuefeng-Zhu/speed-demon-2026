from pathlib import Path
import argparse, tempfile, subprocess, sys
parser=argparse.ArgumentParser()
parser.add_argument('candidate', help='absolute path to compiled candidate')
args=parser.parse_args()
root=Path.cwd()
exe=args.candidate
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

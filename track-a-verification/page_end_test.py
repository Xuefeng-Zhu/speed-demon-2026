import argparse, os, pathlib, subprocess, tempfile
parser = argparse.ArgumentParser()
parser.add_argument('--binary', required=True)
parser.add_argument('--reference', required=True)
args = parser.parse_args()
ref = str(pathlib.Path(args.reference).resolve())
binary = str(pathlib.Path(args.binary).resolve())
prefix='2026-11-02T17:59:59.999999Z GET '
base=prefix+'/ 200 1\n'
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t); d=p/'data'; x=p/'actual'; y=p/'ref'; d.mkdir();x.mkdir();y.mkdir()
 for size in [4094,4095,4096,4097,4098,8191,8192,8193,12287,12288,12289,16383,16384,16385]:
  for n in range(size//len(base), -1,-1):
   padding=size-n*len(base)-len(prefix)-len('/ 599 4294967295\n')
   if 0 <= padding <= 124: break
  else: raise AssertionError(size)
  d.joinpath('requests.log').write_text(base*n+prefix+'/'+'z'*padding+' 599 4294967295\n')
  assert d.joinpath('requests.log').stat().st_size==size
  subprocess.run(['python3',ref,'--data',str(d),'--out',str(y)],check=True,stdout=subprocess.DEVNULL)
  expected=y.joinpath('summary.txt').read_bytes()
  for threads in [1,2,3,6,12,64]:
   env={**os.environ,'SD_DATA':str(d),'SD_OUT':str(x),'SD_THREADS':str(threads)}
   subprocess.run([binary],env=env,check=True)
   assert x.joinpath('summary.txt').read_bytes()==expected,(size,threads)
  print('PASS',size,flush=True)

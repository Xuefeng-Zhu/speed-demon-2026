import pathlib,subprocess,tempfile,sys
binary=sys.argv[1];nshards=int(sys.argv[2]);k=500000
prefix='2026-10-30T18:00:00.000000Z GET '
base=(prefix+'/ 200 1\n').encode(); plus=(prefix+'/x 200 1\n').encode()
endpoint='/'+'z'*124
target=(prefix+endpoint+' 599 4294967295\n').encode()
def filler(n):
 q,r=divmod(n,len(base));assert r<=q
 return base*(q-r)+plus*r,(q-r,r)
with tempfile.TemporaryDirectory() as td:
 path=pathlib.Path(td);data=path/'requests.log';out=path/'summary.txt'
 for boundary in (k,(nshards-1)*k):
  for offset in (1,13,27,34,40,80,140,len(target)-2):
   before,bc=filler(boundary-offset)
   after,ac=filler(nshards*k-len(before)-len(target))
   data.write_bytes(before+target+after)
   assert data.stat().st_size==nshards*k
   subprocess.run([binary,str(data),str(out)],check=True)
   count0=bc[0]+ac[0];count1=bc[1]+ac[1]
   expected=f'2026-10-30T18:00:00Z / {count0} 1 1 1 0 0\n2026-10-30T18:00:00Z /x {count1} 1 1 1 0 0\n2026-10-30T18:00:00Z {endpoint} 1 4294967295 4294967295 4294967295 1 1000000\n'
   assert out.read_text()==expected,(boundary,offset)
   print('PASS',nshards,'shards boundary',boundary,'target offset',offset,flush=True)

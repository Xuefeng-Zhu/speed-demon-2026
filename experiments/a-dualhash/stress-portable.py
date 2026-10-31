import argparse
import datetime,hashlib,os,pathlib,random,subprocess,tempfile
ap=argparse.ArgumentParser();ap.add_argument('--binary',action='append',required=True);ap.add_argument('--reference',required=True);args=ap.parse_args();rng=random.Random(918273);chars='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-_.{}:';names={'/'}
for L in range(2,126):
 for z in range(14):
  names.add('/'+''.join(rng.choice(chars) for _ in range(L-1)))
# Prefix traps and cases differing around 8/16-byte word boundaries.
for L in (7,8,9,15,16,17,23,24,25,31,32,33,63,64,65,124,125):
 for ch in ('a','b','Z','0'):
  names.add('/'+'a'*(L-2)+ch)
assert all(1<=len(s)<=125 for s in names)
endpoints=sorted(names); print('endpoints',len(endpoints),'range',min(map(len,endpoints)),max(map(len,endpoints)))
with tempfile.TemporaryDirectory(prefix='a-hash-review-') as t:
 p=pathlib.Path(t);d=p/'data';d.mkdir();ref=p/'ref';ref.mkdir();out=p/'out';out.mkdir(); rows=[];start=datetime.datetime(2026,10,30,18)
 for i in range(len(endpoints)*4):
  name=endpoints[i%len(endpoints)];hour=(i*37)%72;dt=start+datetime.timedelta(hours=hour,minutes=i%60,seconds=(i//60)%60,microseconds=(i*83)%1000000)
  status=(200,299,499,500,599)[i%5]; lat=(0,9,9999999,4294967295)[(i//3)%4];method=('GET','POST','OPTIONS','DELETE','PATCH')[i%5]
  rows.append(f'{dt:%Y-%m-%dT%H:%M:%S.%fZ} {method} {name} {status} {lat}\n')
 rng.shuffle(rows);(d/'requests.log').write_text(''.join(rows));subprocess.run(['python3',str(pathlib.Path(args.reference).resolve()),'--data',str(d),'--out',str(ref)],check=True)
 expected=(ref/'summary.txt').read_bytes();print('hash',hashlib.sha256(expected).hexdigest())
 for exe in [str(pathlib.Path(x).resolve()) for x in args.binary]:
  for workers in (1,2,3,7,12,32):
   subprocess.run([exe],env=dict(os.environ,SD_DATA=str(d),SD_OUT=str(out),SD_THREADS=str(workers)),check=True)
   assert (out/'summary.txt').read_bytes()==expected,(exe,workers)
  print('PASS',exe,flush=True)

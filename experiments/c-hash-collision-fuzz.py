import csv,random,subprocess,tempfile,sys
from pathlib import Path
from io import StringIO
exe=sys.argv[1];reference=sys.argv[2]
def field(s,quoted):
 return '"'+s.replace('"','""')+'"' if quoted else s
for seed in range(40):
 rng=random.Random(seed)
 with tempfile.TemporaryDirectory(prefix='c-hash-review-') as temp:
  root=Path(temp);data=root/'data';out=root/'out';ref=root/'ref'
  for p in (data,out,ref):p.mkdir()
  (data/'regions.csv').write_text('region_id,country\n1,AAA\n3,BBB\n5,AAA\n7,CCC\n',encoding='ascii')
  names=['', 'A', 'A ', 'A  ', 'Ann "Annie" Lee', 'Quote "', 'X, Y', 'B', 'B ']
  notes=['','x','x\ny','said "yes"','comma, here','"','end ']
  raw=bytearray(b'\xef\xbb\xbfid,name,note,region_id,amount\r\n')
  for i in range(rng.randrange(0,250)):
   name=rng.choice(names);note=rng.choice(notes);namefield=field(name,bool(name) or rng.randrange(2)==0);notefield=field(note,bool(note) or rng.randrange(2)==0)
   cents=rng.randrange(-99999,9999999);amount=('-' if cents<0 else '')+str(abs(cents)//100)+'.'+str(abs(cents)%100).zfill(2)
   if i and rng.randrange(9)==0:raw.extend(b'\xef\xbb\xbf')
   raw.extend((f'{i+1},{namefield},{notefield},{rng.choice([1,2,3,5,7,9000000])},{amount}'+rng.choice(['\n','\r\n'])).encode('ascii'))
  if len(raw)>35 and rng.randrange(2)==0:raw=raw.rstrip(b'\r\n')
  (data/'records.csv').write_bytes(raw)
  subprocess.run([sys.executable,reference,'--data',str(data),'--out',str(ref)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([exe,str(data),str(out)],check=True,stdout=subprocess.DEVNULL)
  assert (out/'aggregates.txt').read_bytes()==(ref/'aggregates.txt').read_bytes(),seed
print('PASS 40 mixed-region collision/CSV corpora')

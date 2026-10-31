import os,subprocess,tempfile
from pathlib import Path
from collections import defaultdict
codes=[chr(65+i//676)+chr(65+(i//26)%26)+chr(65+i%26) for i in range(26**3)]
lookup=[(1+2*i,codes[i%len(codes)]) for i in range(3*len(codes))]+[(999999,'AAA')]
assert len(lookup)==len({k for k,_ in lookup})
def money(v):return ('-' if v<0 else '')+f'{abs(v)//100}.{abs(v)%100:02d}'
with tempfile.TemporaryDirectory(prefix='c-full-codes-') as t:
 root=Path(t);data=root/'data';data.mkdir()
 source=(Path(__file__).parent/'combined.rs').read_text()
 needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'
 assert source.count(needle)==1
 bins={}
 for n in (1,2,7,32):
  src=root/f'candidate-{n}.rs';exe=root/f'candidate-{n}'
  src.write_text(source.replace(needle,f'let n = {n};'))
  subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes',str(src),'-o',str(exe)],check=True)
  bins[n]=exe
 (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{rid},{code}\n' for rid,code in lookup))
 groups=defaultdict(list);records=[]
 cases=[(rid,code) for rid,code in lookup if code!='ZZZ']+[(2,'_UNMATCHED'),(999998,'_UNMATCHED'),(1000000,'_UNMATCHED'),(9999999,'_UNMATCHED')]
 for num,(rid,code) in enumerate(cases,1):
  amount=(-50,0,100)[num%3]; groups[code].append((num,amount))
  bom=b'\xef\xbb\xbf' if num>1 and num%1000==0 else b''
  eol=b'\r\n' if num%2==0 or num==len(cases) else b'\n'
  records.append(bom+f'{num},"X","a\nb",{rid},{money(amount)}'.encode()+eol)
 (data/'records.csv').write_bytes(b'\xef\xbb\xbfid,name,note,region_id,amount\r\n'+b''.join(records))
 expected=[]
 for code,vals in sorted(groups.items()):
  cnt=len(vals);ids=sum(v[0] for v in vals);amounts=[v[1] for v in vals]
  expected.append(f'{code} {cnt} {ids} {money(sum(amounts))} {money(min(amounts))} {money(max(amounts))} 1 {cnt} {cnt*3}\n')
 expected=''.join(expected).encode();assert 'ZZZ' not in groups and len(groups)==17576
 for n in (1,2,7,32):
  out=root/f'out-{n}';out.mkdir();env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out));subprocess.run([str(bins[n])],env=env,check=True,timeout=90)
  got=(out/'aggregates.txt').read_bytes();assert got==expected,(n,got[:200],expected[:200])
print(f'PASS {len(lookup)} region rows, {len(cases)} records, 17,576 code values and unknowns x 4 worker counts')

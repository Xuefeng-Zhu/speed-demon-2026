import ast,json,re,sys
from pathlib import Path

keys=('lengths','hits','probes_hit','probes_miss')
def read(path):
 rows=[]
 for line in Path(path).read_text().splitlines():
  if not line.startswith('B_TOKEN_PROFILE '): continue
  m=re.search(r'lo=(\d+) hi=(\d+)',line); row={'lo':int(m.group(1)),'hi':int(m.group(2))}
  for k in keys:
   match=re.search(rf'{k}=(\[[^\]]*\])',line)
   if not match:raise ValueError(k)
   row[k]=ast.literal_eval(match.group(1))
  if row['hi']-row['lo']>1_000_000:rows.append(row)
 rows.sort(key=lambda r:r['lo'])
 assert rows[0]['lo']==0 and all(a['hi']==b['lo'] for a,b in zip(rows,rows[1:]))
 assert rows[-1]['hi']==253827587
 return {k:[sum(row[k][i] for row in rows) for i in range(len(rows[0][k]))] for k in keys}|{'chunks':len(rows)}
a=read(sys.argv[1]);b=read(sys.argv[2]);assert a==b,'profile changed between runs'
l,h=a['lengths'],a['hits'];a.update(total=sum(l),matched=sum(h),missing=sum(l)-sum(h),short_1_to_3=sum(l[1:4]),short_1_to_4=sum(l[1:5]),short_1_to_8=sum(l[1:9]))
print(json.dumps(a,indent=2))

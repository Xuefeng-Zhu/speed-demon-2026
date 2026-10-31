import random
cuts=set(); cases=0
for seed in range(700):
 r=random.Random(seed); n=r.choice([1,10,100,1000,10000,100000,1000000,1740512]); m=r.randrange(0,90)
 edges=[(r.randrange(n),r.randrange(n),r.choice([0,9,10,99,100,999,1000,4294967295])) for _ in range(m)]
 data=(f'{n} {m}\n'+''.join(f'{u} {v} {w}\n' for u,v,w in edges)).encode()
 for threads in [1,2,3,7,12,16,32,64]:
  result=[]
  for i in range(threads):
   start=1+i*(len(data)-1)//threads; end=1+(i+1)*(len(data)-1)//threads
   buf=data[start-1:min(end+32,len(data))]
   a=buf.index(b'\n')+1; b=buf.index(b'\n',end-start)
   if end<len(data):
    back=data.rfind(b'\n',0,end); forward=data.find(b'\n',end)
    cuts.add(end-back-1)
    assert forward>=0 and forward-end<32
   if a<b:
    fields=buf[a:b+1].split()
    assert len(fields)%3==0
    result.extend(tuple(map(int,fields[j:j+3])) for j in range(0,len(fields),3))
  assert result==edges,(seed,threads)
  cases+=1
print('PASS',cases,'partition cases; covered within-line cut positions',sorted(cuts))

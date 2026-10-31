import argparse,array,heapq,math,random,statistics
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument("--data", required=True)
parser.add_argument("--profile", default="experiments/track-d-frontier-bias/query-times.txt")
args=parser.parse_args()
p=str(Path(args.data).resolve())+"/"
qs=[tuple(map(int,l.split())) for l in open(p+'queries.txt')]
vals={int(a):int(b) for l in open(args.profile) for _,a,b in [l.split()]}; dur=[vals[i] for i in range(len(qs))]
with open(p+'graph.txt') as f:
 n,m=map(int,next(f).split()); out=array.array('I',[0])*n; inn=array.array('I',[0])*n
 for l in f:
  u,v,w=map(int,l.split());out[u]+=1;inn[v]+=1

def ranks(x):
 order=sorted(range(len(x)),key=x.__getitem__); r=[0.0]*len(x); i=0
 while i<len(x):
  j=i+1
  while j<len(x) and x[order[j]]==x[order[i]]:j+=1
  for k in range(i,j):r[order[k]]=(i+j-1)/2
  i=j
 return r

def corr(a,b):
 ra,rb=ranks(a),ranks(b);ma=statistics.mean(ra);mb=statistics.mean(rb)
 num=sum((x-ma)*(y-mb) for x,y in zip(ra,rb));den=math.sqrt(sum((x-ma)**2 for x in ra)*sum((y-mb)**2 for y in rb));return num/den if den else 0

def sim(order, nworkers):
 h=[0]*nworkers
 for i in order:
  t=heapq.heappop(h);heapq.heappush(h,t+dur[i])
 return max(h)/1e9
features={
 'source_out': [out[s] for s,t in qs],
 'target_in': [inn[t] for s,t in qs],
 'min_degree': [min(out[s],inn[t]) for s,t in qs],
 'sum_degree': [out[s]+inn[t] for s,t in qs],
 'product_degree': [out[s]*inn[t] for s,t in qs],
 'source_out_target_in_zero': [int(out[s]>0 and inn[t]>0) for s,t in qs],
}
base=list(range(len(qs))); random.Random(29).shuffle(base)
print('records',len(qs),'total_sum_s',sum(dur)/1e9,'min/median/max_ms',*[round(v/1e6,4) for v in (min(dur),statistics.median(dur),max(dur))])
print('source_order simulated makespan',sim(range(len(qs)),12),'shuffle',sim(base,12),'perfect_greedy',sim(sorted(range(len(qs)),key=lambda i:-dur[i]),12))
for name,feat in features.items():
 order=sorted(range(len(qs)),key=lambda i:-feat[i]); rev=list(reversed(order)); top=sorted(range(len(qs)),key=lambda i:-dur[i])[:100]; print(name,'spearman',round(corr(feat,dur),4),'sched_desc',round(sim(order,12),6),'sched_asc',round(sim(rev,12),6),'top100 mean',round(statistics.mean(feat[i] for i in top),3),'all mean',round(statistics.mean(feat),3),'feature_range',min(feat),max(feat))

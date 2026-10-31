from pathlib import Path
exec((Path(__file__).with_name('features.py').read_text()).split("features={")[0])
outs={s:[] for s,t in qs};ins={t:[] for s,t in qs}
with open(p+'graph.txt') as f:
 next(f)
 for l in f:
  u,v,w=map(int,l.split())
  if u in outs:outs[u].append(v)
  if v in ins:ins[v].append(u)
fw=[sum(out[v] for v in outs[s]) for s,t in qs];bw=[sum(inn[u] for u in ins[t]) for s,t in qs]
features={'source_next_out':fw,'target_prev_in':bw,'min_next':list(map(min,fw,bw)),'max_next':list(map(max,fw,bw)),'sum_next':[a+b for a,b in zip(fw,bw)],'product_next':[a*b for a,b in zip(fw,bw)]}
for name,feat in features.items():
 order=sorted(range(len(qs)),key=lambda i:-feat[i]);top=sorted(range(len(qs)),key=lambda i:-dur[i])[:100];print(name,'spearman',round(corr(feat,dur),4),'schedule',round(sim(order,12),6),'top100 mean',round(statistics.mean(feat[i] for i in top),3),'all mean',round(statistics.mean(feat),3))
flags={'direct_or_self':[s==t or t in outs[s] for s,t in qs], 'two_hop':[s==t or t in outs[s] or bool(set(outs[s]) & set(ins[t])) for s,t in qs]}
for name,flag in flags.items():
 yes=[dur[i] for i,v in enumerate(flag) if v];no=[dur[i] for i,v in enumerate(flag) if not v];order=sorted(range(len(qs)),key=lambda i:flag[i]);print(name,'yes',len(yes),'yes_med_ms',round(statistics.median(yes)/1e6,4) if yes else None,'no_med_ms',round(statistics.median(no)/1e6,4) if no else None,'yes_total_s',round(sum(yes)/1e9,6),'sim_nontrivial_first',round(sim(order,12),6))

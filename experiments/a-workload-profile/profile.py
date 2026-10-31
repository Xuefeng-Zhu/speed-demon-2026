#!/usr/bin/env python3
"""Aggregate public generated Track A workload characteristics; never emits endpoint strings."""
import argparse,collections,json,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
counts=collections.Counter();lens=collections.Counter();lat=collections.Counter();methods=collections.Counter();transitions=0;n=0;last=None
with (a.data/'requests.log').open('rb') as f:
 for row in f:
  ts,method,endpoint,status,latency=row.rstrip(b'\n').split(b' ')
  counts[endpoint]+=1;lens[len(endpoint)]+=1;lat[len(latency)]+=1;methods[method.decode()]+=1
  transitions+=last==endpoint;last=endpoint;n+=1
clusters={}
for label,make in [('prefix8_len',lambda x:(x[:8],len(x))),('prefix16_len',lambda x:(x[:16],len(x))),('ends8_len',lambda x:(x[:8],x[-8:],len(x))),('prefix24_len',lambda x:(x[:24],len(x)))]:
 groups=collections.defaultdict(list)
 for endpoint,frequency in counts.items():groups[make(endpoint)].append(frequency)
 clusters[label]={'groups':len(groups),'colliding_groups':sum(len(v)>1 for v in groups.values()),'records_in_ambiguous_groups':sum(sum(v) for v in groups.values() if len(v)>1),'max_unique_per_group':max(map(len,groups.values()),default=0)}
freq=sorted(counts.values(),reverse=True)
o={'records':n,'unique_endpoints':len(counts),'endpoint_length_histogram':dict(sorted(lens.items())),'latency_digit_histogram':dict(sorted(lat.items())),'methods':dict(methods),'same_as_previous':transitions,'top_endpoint_record_fractions':{str(k):sum(freq[:k])/n for k in (1,2,4,8,16,32,64,128)},'descriptor_ambiguity':clusters,'note':'Seed-specific native data characteristics; not assumptions, outputs or official performance.'}
a.report.write_text(json.dumps(o,indent=2)+'\n');print(json.dumps(o,indent=2))

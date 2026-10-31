#!/usr/bin/env python3
"""phases.py runs binA binB ...: alternate instrumented binaries, print median phase ms."""
import subprocess, sys, os, statistics as st, tempfile, shutil
D='/projects/sandbox/.data'
n=int(sys.argv[1]); bins=sys.argv[2:]; res={b:{} for b in bins}
env0=dict(os.environ, SD_DATA=D+'/speed-b-full', SD_THREADS=os.environ.get('T','8'))
for i in range(n+1):
    for b in bins:
        o=tempfile.mkdtemp(dir='/tmp'); env=dict(env0, SD_OUT=o)
        p=subprocess.run([D+'/bin/'+b],env=env,capture_output=True,text=True)
        shutil.rmtree(o)
        if i==0: continue
        prev=0; ph={}
        for l in p.stderr.splitlines():
            x=l.split()
            if x[0]=='PHASE': ph[x[1]]=(int(x[2])-prev)/1e6; prev=int(x[2])
            if x[0]=='QKIND': ph[x[1]]=int(x[3])/1e6
            if x[0]=='INFO' and x[1].endswith('cyc'): ph[x[1]]=int(x[2])/2.4e6
        ph['total']=prev/1e6
        for k,v in ph.items(): res[b].setdefault(k,[]).append(v)
keys=list(res[bins[0]].keys())
print('%-16s'%'phase'+''.join('%14s'%b[-14:] for b in bins))
for k in keys:
    print('%-16s'%k+''.join('%14.2f'%st.median(res[b].get(k,[0])) for b in bins))

#!/usr/bin/env python3
"""csrper.py <runs> <threads> <bin> [bin ...]: per-chunk CSR and scan cost per stream entry from the
MIDX lines of mkmem.py builds, split into the larger and smaller half of the chunks, plus the summed CSR time."""
import os, subprocess, sys, statistics as st, tempfile, shutil
D='/projects/sandbox/.data'
n=int(sys.argv[1]); t=sys.argv[2]; bins=sys.argv[3:]
for b in bins:
    big=[]; small=[]; scanb=[]; scans=[]; tot=[]
    for i in range(n):
        o=tempfile.mkdtemp(dir=D+'/mem'); env=dict(os.environ, SD_DATA=D+'/speed-b-full', SD_OUT=o, SD_THREADS=t)
        p=subprocess.run([D+'/bin/'+b],env=env,capture_output=True,text=True); shutil.rmtree(o)
        rows=[l.split() for l in p.stderr.splitlines() if l.startswith('MIDX')]
        sl=sorted(int(x[4]) for x in rows); med=sl[len(sl)//2]
        cs=0
        for x in rows:
            slen=int(x[4]); csr=(int(x[11])-int(x[10])); scan=int(x[10])-int(x[9])
            cs+=csr
            (big if slen>=med else small).append(csr/slen)
            (scanb if slen>=med else scans).append(scan/slen)
        tot.append(cs/1e6)
    print(f'{b:22s} t={t} csr ns/entry big {st.median(big):.2f} small {st.median(small):.2f} | scan ns/entry big {st.median(scanb):.1f} small {st.median(scans):.1f} | csr sum {st.median(tot):.1f} ms')

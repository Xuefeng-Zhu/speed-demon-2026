import subprocess,os,tempfile,statistics as st,sys
D='/projects/sandbox/.data'; bins=sys.argv[2:]; R={b:[] for b in bins}
for i in range(int(sys.argv[1])):
  for b in bins:
    o=tempfile.mkdtemp(); p=subprocess.run([D+'/bin/'+b],env=dict(os.environ,SD_DATA=D+'/speed-b-full',SD_OUT=o,SD_THREADS=os.environ.get('T','8')),capture_output=True,text=True)
    rows=[l.split() for l in p.stderr.splitlines() if l.startswith('SCAN')]
    nt=sum(int(r[9]) for r in rows)
    R[b].append([sum(int(r[j]) for r in rows)/nt for j in (3,4,5,6,8,18)])
for b in bins:
    v=R[b]; print('%-12s'%b+' '.join('%s %.1f'%(n,st.median(x[j] for x in v)) for j,n in enumerate(['masks','lookup','cb','phrase','csr','total'])))

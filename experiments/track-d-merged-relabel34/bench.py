import subprocess,time,os,hashlib,statistics,sys,resource
bins=sys.argv[2:]; n=int(sys.argv[1]); env=dict(os.environ,SD_DATA='full',SD_OUT='out'); res={b:[] for b in bins}
H='a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e'
for i in range(n):
  for b in (bins if i%2==0 else bins[::-1]):
    t=time.perf_counter(); subprocess.run([b],env=env,check=True); res[b].append(time.perf_counter()-t)
    assert hashlib.sha256(open('out/distances.txt','rb').read()).hexdigest()==H
for b in bins: print(f"{b:32s} median {statistics.median(res[b])*1e3:6.1f} ms  min {min(res[b])*1e3:6.1f}")

import hashlib,json,subprocess,time
from pathlib import Path
expected='d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536'
name='sd-c-prewarm-isolated'
base=['docker','run','--rm','--network=none','--read-only','-v','/tmp/sdc-full:/data:ro','--entrypoint','/bin/sh']
pre=subprocess.Popen(base[:2]+['--name',name]+base[2:]+['local-c-cgroup-current','-c','cat /data/records.csv >/dev/null && cat /data/regions.csv >/dev/null && echo READY && sleep 120'],stdout=subprocess.PIPE,text=True)
try:
 if pre.stdout.readline().strip()!='READY': raise RuntimeError('prewarm failed')
 rows=[]
 for i in range(3):
  order=['current','mmap'] if i%2==0 else ['mmap','current']
  for kind in order:
   out=Path('/tmp/c-cgroup-out-'+kind); f=out/'aggregates.txt';f.unlink(missing_ok=True)
   cmd=['docker','run','--rm','--network=none','--read-only','--tmpfs','/tmp:rw,size=1g,exec','--memory=8g','--memory-swap=8g','--pids-limit=512','--cap-drop=ALL','--security-opt=no-new-privileges','--user','65534:65534','--ulimit','nofile=8192:8192','-e','TRACK=c','-v','/tmp/sdc-full:/data:ro','-v',f'{out}:/out:rw','--entrypoint','/bin/sh','local-c-cgroup-'+kind,'-c','/app/solution && cat /sys/fs/cgroup/memory.peak']
   start=time.perf_counter(); value=subprocess.check_output(cmd,text=True).strip();elapsed=time.perf_counter()-start
   digest=hashlib.sha256(f.read_bytes()).hexdigest()
   if digest!=expected:raise RuntimeError(f'wrong {kind} hash {digest}')
   row={'iteration':i,'variant':kind,'container_elapsed_including_startup_s':elapsed,'memory_peak_bytes':int(value),'sha256':digest}
   rows.append(row);print(json.dumps(row),flush=True)
 Path('/tmp/c-cgroup-report.json').write_text(json.dumps(rows,indent=2)+'\n')
finally:
 subprocess.run(['docker','stop',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
 pre.wait(timeout=10)

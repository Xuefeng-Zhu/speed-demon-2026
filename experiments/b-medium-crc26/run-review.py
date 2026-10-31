#!/usr/bin/env python3
from pathlib import Path
import platform,subprocess,sys,tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'experiments/b-medium-crc26/candidate.rs').read_text()
tail=(root/'experiments/b-crc-medium-review/review-tail.rs').read_text()
tail+=(root/'experiments/b-crc-medium-review/threshold-tail.rs').read_text()
actual='--x86-v3' in sys.argv[1:]
if actual and (platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64')): raise SystemExit('requires Linux x86-64')
flags=['-C','target-cpu=x86-64-v3'] if actual else ['--cfg','b_medium_crc_emulate']
with tempfile.TemporaryDirectory() as d:
 for forced in [False,True]:
  p=Path(d)/('forced.rs' if forced else 'normal.rs');p.write_text(source+'\n'+tail);exe=p.with_suffix('')
  extra=['--cfg','b_medium_crc_forced'] if forced else []
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*flags,*extra,str(p),'-o',str(exe)],check=True)
  result=subprocess.run([str(exe),'--nocapture'],check=True,capture_output=True,text=True);print(result.stdout)
  if 'medium_review::exact_keys_and_fallback ... ok' not in result.stdout: raise SystemExit('medium tests did not run')

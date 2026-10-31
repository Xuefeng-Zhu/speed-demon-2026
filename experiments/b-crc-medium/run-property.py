#!/usr/bin/env python3
from pathlib import Path
import platform, subprocess, sys, tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'experiments/b-crc-medium/candidate.rs').read_text()
old=(root/'experiments/b-short-lookup/candidate-property.rs').read_text()
tests=old[old.index('#[cfg(test)]\nmod independent'):]
tests=tests.replace('p.build_short();','p.build_short();p.build_medium();')
tests+=(root/'experiments/b-crc-medium/property-tail.rs').read_text()
actual='--x86-v3' in sys.argv[1:]
if actual and (platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64')):raise SystemExit('requires Linux x86-64')
flags=['-C','target-cpu=x86-64-v3'] if actual else ['--cfg','b_medium_crc_emulate']
with tempfile.TemporaryDirectory() as d:
 for forced in (False,True):
  p=Path(d)/('forced.rs' if forced else 'normal.rs'); tail=tests.replace('run(100000)','run(5000)' if forced else 'run(100000)');p.write_text(source+'\n'+tail)
  binary=p.with_suffix('');extra=['--cfg','b_medium_crc_forced'] if forced else []
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*flags,*extra,str(p),'-o',str(binary)],check=True)
  r=subprocess.run([str(binary),'--nocapture'],check=True,capture_output=True,text=True);print(r.stdout)
  required='medium_properties::forced_fallback ... ok' if forced else 'medium_properties::fallback_thresholds ... ok'
  if required not in r.stdout:raise SystemExit('fallback test did not run')
  if actual and 'medium_guard::protected_page_boundaries ... ok' not in r.stdout:raise SystemExit('SSE4.2 guard test did not run')

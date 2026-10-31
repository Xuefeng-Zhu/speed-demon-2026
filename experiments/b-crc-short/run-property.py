#!/usr/bin/env python3
from pathlib import Path
import platform,subprocess,sys,tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'experiments/b-crc-short/candidate.rs').read_text()
old=(root/'experiments/b-short-lookup/candidate-property.rs').read_text()
tests=old[old.index('#[cfg(test)]\nmod independent'):]+(root/'experiments/b-crc-short/property-tail.rs').read_text()
actual='--x86-v3' in sys.argv[1:]
if actual and (platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64')):
 raise SystemExit('--x86-v3 requires Linux x86-64')
flags=['-C','target-cpu=x86-64-v3'] if actual else ['--cfg','b_crc_emulate']
with tempfile.TemporaryDirectory() as d:
 for forced in (False,True):
  p=Path(d)/('forced.rs' if forced else 'normal.rs')
  independent='' if forced else (root/'experiments/b-crc-short/independent-tests.rs').read_text()
  p.write_text(source+'\n'+tests.replace('run(100000)','run(5000)' if forced else 'run(100000)')+'\n'+independent)
  binary=p.with_suffix('');extra=['--cfg','b_crc_forced_collision'] if forced else []
  subprocess.run(['rustc','--edition=2021','--test','-O','-C','overflow-checks=yes',*flags,*extra,str(p),'-o',str(binary)],check=True)
  r=subprocess.run([str(binary),'--nocapture'],check=True,capture_output=True,text=True);print(r.stdout)
  required='crc_properties::insertion_guard_fallback ... ok' if forced else 'crc_properties::cyclic_cluster_guard ... ok'
  if required not in r.stdout:raise SystemExit('required collision guard did not run')
  if not forced and 'edge_review::boundary_on_wrapping_cluster ... ok' not in r.stdout:raise SystemExit('independent edge review did not run')
  if actual and 'crc_guard_pages::short_lookup_at_guard_pages ... ok' not in r.stdout:raise SystemExit('actual SSE4.2 guarded-page test did not run')

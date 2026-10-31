#!/usr/bin/env python3
"""Exercise actual SSE4.2 CRC, a PROT_NONE guard page, and Track A reference tests."""
import hashlib, os, pathlib, platform, subprocess, sys, tempfile
here=pathlib.Path(__file__).resolve().parent
root=here.parent.parent
if sys.platform != 'linux' or platform.machine().lower() not in ('x86_64','amd64'):
    sys.exit('This preflight requires Linux x86-64 with SSE4.2; no tests were run.')
if os.sysconf('SC_PAGE_SIZE') != 4096:
    sys.exit('This guard test requires a 4096-byte Linux page size; no tests were run.')
flags=pathlib.Path('/proc/cpuinfo').read_text()
if not any('sse4_2' in line.split(':',1)[-1].split() for line in flags.splitlines() if line.startswith('flags')):
    sys.exit('SSE4.2 not reported; no tests were run.')
source=(here/'candidate.rs').read_bytes()
assert hashlib.sha256(source).hexdigest() == '9028986cf2546dfc008cf05dfdb32648cf64b6536223b933fe820cd69deb89e9'
with tempfile.TemporaryDirectory(prefix='a-crc-linux-preflight-') as tmp:
    tmp=pathlib.Path(tmp)
    test=tmp/'candidate_test.rs'; test.write_bytes(source+b'\n'+(here/'linux_preflight_tail.rs').read_bytes())
    binary=tmp/'guard_test'
    subprocess.run(['rustc','--edition=2021','--test','-C','opt-level=3','-C','overflow-checks=no','-C','target-feature=+sse4.2',str(test),'-o',str(binary)],check=True)
    subprocess.run([str(binary),'--nocapture'],check=True)
    candidate=tmp/'candidate'; base=tmp/'base'
    for src,out in ((here/'candidate.rs',candidate),(here/'baseline.rs',base)):
        subprocess.run(['rustc','--edition=2021','-C','opt-level=3','-C','overflow-checks=no','-C','target-feature=+sse4.2',str(src),'-o',str(out)],check=True)
    subprocess.run(['python3',str(root/'track-a-verification/test.py'),'--binary',str(candidate),'--io','directories'],check=True)
    subprocess.run(['python3',str(root/'track-a-verification/page_end_test.py'),'--binary',str(candidate),'--reference',str(root/'official/reference/a_ingest.py')],check=True)
print('LINUX_PREFLIGHT_PASS: actual SSE4.2 hardware path and guard, synthetic and page-end reference tests.')

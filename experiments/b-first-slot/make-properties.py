#!/usr/bin/env python3
"""Append exact-source probe properties; no benchmark."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--expected-sha');a=p.parse_args()
raw=a.source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
if a.expected_sha:assert sha==a.expected_sha
s=raw.decode();assert s.count('fn main() {')==1
s=s.replace('fn main() {','fn unused_program_main() {')+'\n'+(Path(__file__).resolve().parent/'properties.rs').read_text()
a.output.write_text(s);print(json.dumps({'source_sha256':sha,'property_source_sha256':hashlib.sha256(s.encode()).hexdigest()}))

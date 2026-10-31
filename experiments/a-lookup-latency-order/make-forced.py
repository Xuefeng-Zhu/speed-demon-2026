#!/usr/bin/env python3
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--forced',action='store_true');p.add_argument('--trace',action='store_true');a=p.parse_args()
s=Path(a.source).read_text()
if a.forced:
 needle='let id = c.table.find(d, h, s, e) as u64;';assert s.count(needle)==1;s=s.replace(needle,'let id = c.table.find(d, 0, s, e) as u64;')
if a.trace:
 needle="    // One global table over all chunks; an endpoint's rank in byte order is its output position."
 trace='''    let (mut ne,mut ni,mut nl)=(0usize,0usize,0usize);
    for r in chunks.iter().flat_map(|c| c.escapes.iter()).flatten() {ne+=1;ni+=usize::from((*r>>33)>=2048);nl+=usize::from((*r as u32)>=0x000f_ffff);}
    eprintln!("ESCAPE total={ne} id={ni} latency={nl}");
''';assert s.count(needle)==1;s=s.replace(needle,trace+needle)
Path(a.output).write_text(s)

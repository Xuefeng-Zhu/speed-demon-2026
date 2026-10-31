#!/usr/bin/env python3
from pathlib import Path
s=Path("candidate.rs").read_text(); p=Path("property.rs").read_text()
a=s.index("        let start = top.len() as u32;\n        let (mut count, mut sum)")
b=s.index("        (count, start, sum)",a)+len("        (count, start, sum)")
assert s[a:b] in p, "property does not contain exact candidate aggregation block"
print("PASS: property contains exact candidate aggregation block")

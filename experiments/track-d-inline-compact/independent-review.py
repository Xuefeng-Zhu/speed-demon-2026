#!/usr/bin/env python3
"""Compile and run an independent exact-source CSR layout check."""
from pathlib import Path
import subprocess, sys, tempfile
source=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name("meeting.rs")
tail = '\n#[cfg(test)]\nmod independent_review {\n    use super::*;\n    fn run(n: usize, t: usize, edges: &[(u32,u32,u32)]) {\n        let mut buckets = (0..t).map(|_| (0..t).map(|_| Vec::new()).collect::<Vec<_>>()).collect::<Vec<_>>();\n        for (i,&(u,v,w)) in edges.iter().enumerate() { buckets[i % t][u as usize * t / n].push((u,v,w)); }\n        let mut expect=vec![Vec::new();n];\n        for parts in &buckets { for block in parts { for &(u,v,w) in block { expect[u as usize].push((v,w as u64)); } } }\n        let csr=build_csr(n, edges.len(), t, buckets);\n        assert_eq!(csr.rows.len(), n);\n        for (u, expected) in expect.iter().enumerate() { assert_eq!(csr.edges(u as u32).collect::<Vec<_>>(), *expected, "n={n}, t={t}, u={u}"); }\n    }\n    #[test]\n    fn many_dimensions_and_edge_orders() {\n        let mut z=0x123456789abcdef0u64;\n        for n in [1,2,3,4,5,7,8,9,16,17,31,32,33,64,97] {\n          for t in [1,2,3,7,12,32] {\n            for m in [0,1,3,4,5,6,31,400] {\n              let mut edges=Vec::new();\n              for i in 0..m {\n                z^=z<<13;z^=z>>7;z^=z<<17;\n                let u=if i % 3 == 0 {0} else {(z as usize % n) as u32};\n                let v=((z >> 13) as usize % n) as u32;\n                let w=match i % 5 {0=>0,1=>u32::MAX,_=>z as u32};\n                edges.push((u,v,w));\n              }\n              run(n,t,&edges);\n            }\n          }\n        }\n    }\n    #[test]\n    fn extreme_skew_and_duplicates() {\n        let mut edges=vec![(0,0,0); 200_000];\n        for i in 0..20_000 { edges.push((0,(i%37) as u32, if i%2==0 {0} else {u32::MAX})); }\n        for t in [1,2,7,32] { run(37,t,&edges); }\n    }\n}\n'
with tempfile.TemporaryDirectory(prefix="d-inline-review-") as tmp:
    test=Path(tmp)/"review.rs"
    binary=Path(tmp)/"review"
    test.write_text(source.read_text() + tail)
    subprocess.run(["rustc","--edition=2021","-O","-C","overflow-checks=yes","--test",str(test),"-o",str(binary)],check=True)
    subprocess.run([str(binary),"--test-threads=1"],check=True)

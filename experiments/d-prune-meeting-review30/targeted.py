#!/usr/bin/env python3
"""Run a minimized meeting-before-prune and exact-fallback regression."""
import hashlib
import pathlib
import subprocess
import tempfile

here = pathlib.Path(__file__).resolve().parent
candidate = here.parent / "track-d-coarse-forward-prune29" / "candidate.rs"
source = candidate.read_text()
assert hashlib.sha256(source.encode()).hexdigest() == "c33d3984871fb22ed7c2d678b3a3562ac82d46cb952a8a0461980301c5a553ef"
needle = "if other != 0 { best = best.min(nd + (!other) as u64); }"
assert source.count(needle) == 1
marker = "const POOL_CAP: usize = 65_536;"
assert source.count(marker) == 1

tail = r'''
#[cfg(test)] static IMPROVE: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
#[cfg(test)] static IMPROVE_NARROW: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
#[cfg(test)] mod targeted {
    use super::*;
    use std::sync::atomic::Ordering::Relaxed;
    fn csr(n:usize, edges:&[(usize,usize,u32)], rev:bool)->Csr {
        let mut rows=vec![Vec::new();n];
        for &(u,v,w) in edges { let (a,b)=if rev {(v,u)} else {(u,v)}; rows[a].push((b,w)); }
        let mut first=Vec::new();let mut compact=Vec::new();let mut wide=Vec::new();
        for row in rows {first.push(compact.len() as u32);for (v,w) in row {
            compact.push((w.min(2047)<<21)|v as u32);wide.push(w);
        }}
        first.push(compact.len() as u32);Csr {first,adj:Vec::new(),compact,wide}
    }
    fn oracle(n:usize, edges:&[(usize,usize,u32)], s:usize, t:usize)->u64 {
        let mut d=vec![NONE;n];d[s]=0;
        for _ in 0..n {for &(u,v,w) in edges {d[v]=d[v].min(d[u].saturating_add(w as u64));}}
        d[t]
    }
    fn check(edges:&[(usize,usize,u32)], expect_hit:bool) {
        let n=13;let graphs=[csr(n,edges,false),csr(n,edges,true)];
        let expected=oracle(n,edges,12,10);assert_eq!(expected,5_000_000_065);
        IMPROVE.store(0,Relaxed);IMPROVE_NARROW.store(0,Relaxed);
        let (fast,dropped)=Search32::new(n).distance([&graphs[0],&graphs[1]],12,10);
        let improvements=IMPROVE.load(Relaxed);let below=IMPROVE_NARROW.load(Relaxed);
        let actual=if fast<u32::MAX as u64 || !dropped {fast} else {
            Search::new(n).distance([&graphs[0],&graphs[1]],12,10)
        };
        assert_eq!(actual,expected);assert_eq!(below,0);
        if expect_hit && POOL_CAP==65_536 {assert!(improvements>0);assert!(dropped);}
        println!("cap={} mutant={} fast={} dropped={} improvements={} narrow_improvements={} final={}",
            POOL_CAP,MUTANT,fast,dropped,improvements,below,actual);
    }
    #[test] fn meeting_then_exact_fallback() {
        let e=vec![(3,10,1_000_000_000),(6,3,3_000_000_000),(7,3,3_000_000_000),
            (8,10,4_000_000_000),(11,3,4_000_000_000),(12,0,2046),
            (12,8,3_500_000_000),(12,11,65)];
        check(&e,true);
        let mut more=e.clone();more.extend([(0,0,0),(3,3,0),(12,0,2046)]);check(&more,false);
    }
}
'''

with tempfile.TemporaryDirectory(prefix="d-meeting-review30-") as temp:
    root = pathlib.Path(temp)
    for mutant in (False, True):
        update = "" if mutant else "best = best.min(nd + (!other) as u64);"
        branch = ("if other != 0 { let meeting = nd + (!other) as u64; "
                  "if meeting < best { IMPROVE.fetch_add(1, std::sync::atomic::Ordering::Relaxed); "
                  "if meeting < u32::MAX as u64 { IMPROVE_NARROW.fetch_add(1, std::sync::atomic::Ordering::Relaxed); } } "
                  + update + " }")
        for cap in (0, 1, 2, 16, 65_536):
            path = root / f"case-{int(mutant)}-{cap}.rs"
            binary = path.with_suffix("")
            path.write_text(source.replace(needle, branch).replace(marker, f"const POOL_CAP: usize = {cap};")
                            + f"\n#[cfg(test)] const MUTANT: bool = {str(mutant).lower()};\n" + tail)
            subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C", "overflow-checks=yes",
                            "-C", "debug-assertions=yes", str(path), "-o", str(binary)], check=True)
            subprocess.run([str(binary), "--nocapture", "--test-threads=1"], check=True)
print("PASS: meeting branch, zero/parallel variant, oracle, and forced-cap fallbacks")

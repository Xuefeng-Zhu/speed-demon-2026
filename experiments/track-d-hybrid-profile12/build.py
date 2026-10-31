#!/usr/bin/env python3
"""Make a diagnostic-only instrumented copy of the exact selected D source."""
from hashlib import sha256
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
data = (root / 'track-d/src/main.rs').read_text()
expected = '671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c'
assert sha256(data.encode()).hexdigest() == expected

def replace(old, new):
    global data
    assert data.count(old) == 1, (old[:100], data.count(old))
    data = data.replace(old, new, 1)

replace('use std::thread;\n', 'use std::thread;\nuse std::time::Instant;\n')
replace('    let file = File::open(path).unwrap();\n', '    let profile_start = Instant::now();\n    let file = File::open(path).unwrap();\n')
replace('    let (fwd, bwd): (Vec<_>, Vec<_>) = buckets.into_iter().map(|[f, b]| (f, b)).unzip();\n',
        '    eprintln!("D_PROFILE parse_bucket_ms={:.3}", profile_start.elapsed().as_secs_f64()*1000.0);\n    let profile_csr = Instant::now();\n    let (fwd, bwd): (Vec<_>, Vec<_>) = buckets.into_iter().map(|[f, b]| (f, b)).unzip();\n')
replace('    let fwd = build_csr(n, m, threads, fwd); // frees the forward buckets before\n    [fwd, build_csr(n, m, threads, bwd)] // the backward graph is allocated\n',
        '    let fwd = build_csr(n, m, threads, fwd);\n    eprintln!("D_PROFILE csr_forward_ms={:.3}", profile_csr.elapsed().as_secs_f64()*1000.0);\n    let profile_csr2 = Instant::now();\n    let bwd = build_csr(n, m, threads, bwd);\n    eprintln!("D_PROFILE csr_backward_ms={:.3}", profile_csr2.elapsed().as_secs_f64()*1000.0);\n    [fwd, bwd]\n')
replace('struct FastHeap { nodes: Vec<PoolNode>, head: [u32;65], free: u32, count: usize, last: u64 }',
        'struct FastHeap { nodes: Vec<PoolNode>, head: [u32;65], free: u32, count: usize, last: u64, pushes: u64, pops: u64, redistributions: u64, min_scans: u64, moves: u64, max_live: usize }')
replace('Self { nodes: Vec::with_capacity(POOL_CAP), head:[END;65], free:END, count:0, last:0 }',
        'Self { nodes: Vec::with_capacity(POOL_CAP), head:[END;65], free:END, count:0, last:0, pushes:0, pops:0, redistributions:0, min_scans:0, moves:0, max_live:0 }')
replace('        self.nodes[id as usize]=PoolNode{key:k,vertex:v,next:self.head[i]};self.head[i]=id;self.count+=1;true\n',
        '        self.nodes[id as usize]=PoolNode{key:k,vertex:v,next:self.head[i]};self.head[i]=id;self.count+=1;self.pushes+=1;self.max_live=self.max_live.max(self.count);true\n')
replace('            let i=self.head.iter().position(|&v|v!=END)?;\n            let mut id=self.head[i];let mut low=u64::MAX;\n            while id!=END {let node=self.nodes[id as usize];low=low.min(node.key);id=node.next;}\n',
        '            let i=self.head.iter().position(|&v|v!=END)?;\n            self.redistributions+=1;\n            let mut id=self.head[i];let mut low=u64::MAX;\n            while id!=END {self.min_scans+=1;let node=self.nodes[id as usize];low=low.min(node.key);id=node.next;}\n')
replace('            while id!=END {let node=self.nodes[id as usize];let j=self.slot(node.key);self.nodes[id as usize].next=self.head[j];self.head[j]=id;id=node.next;}\n',
        '            while id!=END {self.moves+=1;let node=self.nodes[id as usize];let j=self.slot(node.key);self.nodes[id as usize].next=self.head[j];self.head[j]=id;id=node.next;}\n')
replace('        let id=self.head[0];debug_assert_ne!(id,END);let node=self.nodes[id as usize];self.head[0]=node.next;\n',
        '        self.pops+=1;let id=self.head[0];debug_assert_ne!(id,END);let node=self.nodes[id as usize];self.head[0]=node.next;\n')
replace('struct Search32 { dist:Vec<[u32;2]>, touched:Vec<u32>, heaps:[FastHeap;2] }',
        '#[derive(Default)]\nstruct Stats { queries:u64, reaches:u64, improves:u64, stale:u64, cutoff_edges:u64, exhaustions:u64, touched:u64 }\nstruct Search32 { dist:Vec<[u32;2]>, touched:Vec<u32>, heaps:[FastHeap;2], stats:Stats }')
replace('Self {dist:vec![[0;2];n],touched:Vec::with_capacity(n),heaps:[FastHeap::new(),FastHeap::new()]}',
        'Self {dist:vec![[0;2];n],touched:Vec::with_capacity(n),heaps:[FastHeap::new(),FastHeap::new()],stats:Stats::default()}')
replace('    fn reach(&mut self,side:usize,v:u32,d:u64)->Result<bool,()> {\n        let slot=',
        '    fn reach(&mut self,side:usize,v:u32,d:u64)->Result<bool,()> {\n        self.stats.reaches+=1;\n        let slot=')
replace('        if d<u32::MAX as u64 && d<(!slot[side]) as u64 {\n            if *slot==[0;2]',
        '        if d<u32::MAX as u64 && d<(!slot[side]) as u64 {\n            self.stats.improves+=1;\n            if *slot==[0;2]')
replace('    fn distance(&mut self,graphs:[&Csr;2],s:u32,t:u32)->(u64,bool) {\n        if s==t',
        '    fn distance(&mut self,graphs:[&Csr;2],s:u32,t:u32)->(u64,bool) {\n        self.stats.queries+=1;\n        if s==t')
replace('            if d>(!self.dist[u as usize][side]) as u64 {continue;}\n',
        '            if d>(!self.dist[u as usize][side]) as u64 {self.stats.stale+=1;continue;}\n')
replace('                if nd>=u32::MAX as u64 {dropped=true;continue;}\n',
        '                if nd>=u32::MAX as u64 {self.stats.cutoff_edges+=1;dropped=true;continue;}\n')
replace("                    Err(())=>{exhausted=true;break 'search;},\n", "                    Err(())=>{self.stats.exhaustions+=1;exhausted=true;break 'search;},\n")
replace('        for &v in &self.touched {self.dist[v as usize]=[0;2];}\n',
        '        self.stats.touched+=self.touched.len() as u64;\n        for &v in &self.touched {self.dist[v as usize]=[0;2];}\n')
replace('    let dir = |key, default: &str| std::env::var(key).unwrap_or(default.to_string());\n',
        '    let total_start=Instant::now();\n    let dir = |key, default: &str| std::env::var(key).unwrap_or(default.to_string());\n')
replace('    let [fwd, bwd] = load_graph(&format!("{data}/graph.txt"), threads);\n',
        '    let [fwd, bwd] = load_graph(&format!("{data}/graph.txt"), threads);\n    eprintln!("D_PROFILE load_total_ms={:.3} threads={}",total_start.elapsed().as_secs_f64()*1000.0,threads);\n')
replace('    let next = AtomicUsize::new(0);\n    thread::scope(|sc| {\n',
        '    let next = AtomicUsize::new(0);\n    let query_start=Instant::now();\n    thread::scope(|sc| {\n')
replace('                let mut fallback: Option<Search> = None;\n                loop {\n',
        '                let mut fallback: Option<Search> = None;\n                let worker_start=Instant::now();\n                let mut fallback_count=0u64;\n                let mut fallback_ms=0.0f64;\n                loop {\n')
replace('                        fallback.get_or_insert_with(|| Search::new(fwd.first.len() - 1))\n                            .distance([&fwd, &bwd], s, t)\n',
        '                        fallback_count+=1;let fallback_start=Instant::now();\n                        let answer=fallback.get_or_insert_with(|| Search::new(fwd.first.len() - 1)).distance([&fwd, &bwd], s, t);\n                        fallback_ms+=fallback_start.elapsed().as_secs_f64()*1000.0;answer\n')
replace('                    answers[i].store(answer, Relaxed);\n                }\n            });\n',
        '''                    answers[i].store(answer, Relaxed);
                }
                let x=&search.stats;let a=&search.heaps[0];let b=&search.heaps[1];
                eprintln!("D_WORKER queries={} reaches={} improves={} pops={} stale={} cutoffs={} exhausted={} touched={} fallback={} fallback_ms={:.3} worker_ms={:.3} heap_push={} heap_redist={} heap_scan={} heap_move={} max_heap={}",
                    x.queries,x.reaches,x.improves,a.pops+b.pops,x.stale,x.cutoff_edges,x.exhaustions,x.touched,fallback_count,fallback_ms,worker_start.elapsed().as_secs_f64()*1000.0,a.pushes+b.pushes,a.redistributions+b.redistributions,a.min_scans+b.min_scans,a.moves+b.moves,a.max_live.max(b.max_live));
            });
''')
replace('    let text: String = answers\n', '    eprintln!("D_PROFILE query_ms={:.3}",query_start.elapsed().as_secs_f64()*1000.0);\n    let text: String = answers\n')
replace('    fs::write(format!("{out}/distances.txt"), text).unwrap();\n',
        '    fs::write(format!("{out}/distances.txt"), text).unwrap();\n    eprintln!("D_PROFILE total_ms={:.3}",total_start.elapsed().as_secs_f64()*1000.0);\n')
Path(sys.argv[1]).write_text(data)

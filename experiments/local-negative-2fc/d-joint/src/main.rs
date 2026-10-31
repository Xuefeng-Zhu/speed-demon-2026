use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::sync::atomic::{AtomicUsize, Ordering};

fn number(b: &[u8], p: &mut usize) -> u32 {
    let mut x = 0u32;
    while *p < b.len() && b[*p] > b' ' { x = x * 10 + (b[*p] - b'0') as u32; *p += 1; }
    while *p < b.len() && b[*p] <= b' ' { *p += 1; }
    x
}
struct Graph { offsets: Vec<usize>, edges: Vec<(u32,u32)> }
struct Search { d: [Vec<u64>;2], seen: [Vec<u16>;2], epoch: u16 }
impl Search {
    fn new(n:usize) -> Self { Self {d:[vec![0;n],vec![0;n]],seen:[vec![0;n],vec![0;n]],epoch:0} }
    fn run(&mut self, gs: [&Graph;2], s:usize, t:usize) -> Option<u64> {
        if s==t { return Some(0); }
        if gs[0].offsets[s]==gs[0].offsets[s+1] || gs[1].offsets[t]==gs[1].offsets[t+1] { return None; }
        if self.epoch == u16::MAX {
            self.seen[0].fill(0);
            self.seen[1].fill(0);
            self.epoch = 0;
        }
        self.epoch += 1;
        let epoch = self.epoch;
        let mut q = [BinaryHeap::new(), BinaryHeap::new()];
        for (k,v) in [s,t].into_iter().enumerate() { self.d[k][v]=0; self.seen[k][v]=epoch; q[k].push(Reverse((0u64,v))); }
        let mut best = u64::MAX;
        loop {
            for (k,heap) in q.iter_mut().enumerate() {
                while let Some(&Reverse((d,v)))=heap.peek() {
                    if self.d[k][v] == d {break;} heap.pop();
                }
            }
            if q[0].is_empty() || q[1].is_empty() { break; }
            let a = q[0].peek().unwrap().0.0; let b = q[1].peek().unwrap().0.0;
            if a + b >= best {break;}
            let k = if a <= b {0} else {1};
            let Reverse((d,v))=q[k].pop().unwrap();
            let g=gs[k];
            for &(to,w) in &g.edges[g.offsets[v]..g.offsets[v+1]] {
                let to=to as usize; let nd=d+w as u64;
                if self.seen[k][to]!=epoch || nd<self.d[k][to] {
                    self.seen[k][to]=epoch; self.d[k][to]=nd; q[k].push(Reverse((nd,to)));
                    if self.seen[1-k][to]==epoch { best=best.min(nd+self.d[1-k][to]); }
                }
            }
        }
        if best==u64::MAX {None} else {Some(best)}
    }
}
fn main() {
    let data=std::env::var("DATA_DIR").unwrap_or_else(|_| "/data".into());
    let out=std::env::var("OUT_DIR").unwrap_or_else(|_| "/out".into());
    let b=std::fs::read(format!("{data}/graph.txt")).unwrap(); let mut p=0;
    let n=number(&b,&mut p) as usize; let m=number(&b,&mut p) as usize;
    let mut es=Vec::with_capacity(m);
    let mut foff=vec![0usize;n+1]; let mut boff=vec![0usize;n+1];
    for _ in 0..m {
        let u=number(&b,&mut p);let v=number(&b,&mut p);let w=number(&b,&mut p);
        foff[u as usize+1]+=1;boff[v as usize+1]+=1;es.push((u,v,w));
    }
    drop(b);
    for i in 1..=n { foff[i]+=foff[i-1];boff[i]+=boff[i-1]; }
    let mut fnxt=foff.clone(); let mut bnxt=boff.clone();
    let mut fedges=vec![(0u32,0u32);m];let mut bedges=vec![(0u32,0u32);m];
    for (u,v,w) in es {let u=u as usize;let v=v as usize;fedges[fnxt[u]]=(v as u32,w);fnxt[u]+=1;bedges[bnxt[v]]=(u as u32,w);bnxt[v]+=1;}
    drop(fnxt);drop(bnxt);
    let forward=Graph{offsets:foff,edges:fedges};let backward=Graph{offsets:boff,edges:bedges};
    let b=std::fs::read(format!("{data}/queries.txt")).unwrap(); let mut p=0; let mut queries=Vec::new();
    while p<b.len() { queries.push((number(&b,&mut p) as usize,number(&b,&mut p) as usize)); }
    let next=AtomicUsize::new(0);
    let results: Vec<_> = (0..queries.len()).map(|_| std::sync::OnceLock::new()).collect();
    std::thread::scope(|scope| {
        for _ in 0..6.min(queries.len()) { scope.spawn(|| {
            let mut search=Search::new(n);
            loop { let i=next.fetch_add(1,Ordering::Relaxed); if i>=queries.len() {break;}
                let (s,t)=queries[i]; results[i].set(search.run([&forward,&backward],s,t)).unwrap();
            }
        }); }
    });
    use std::fmt::Write;
    let mut output=String::new();
    for result in results { match result.into_inner().unwrap() { Some(x)=>writeln!(output,"{x}").unwrap(),None=>writeln!(output,"-1").unwrap() } }
    std::fs::write(format!("{out}/distances.txt"),output).unwrap();
}

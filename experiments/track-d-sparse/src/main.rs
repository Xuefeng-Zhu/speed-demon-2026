use std::cmp::Reverse;
use std::collections::{BinaryHeap,HashMap};
use std::hash::{BuildHasherDefault, Hasher};
#[derive(Default)]
struct IntHasher(u64);
impl Hasher for IntHasher {
    fn finish(&self) -> u64 { self.0 }
    fn write(&mut self, _: &[u8]) { unreachable!() }
    fn write_usize(&mut self, x: usize) {
        let mut z = (x as u64).wrapping_add(0x9e3779b97f4a7c15);
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
        self.0 = z ^ (z >> 31);
    }
}
type Dist = HashMap<usize,u64,BuildHasherDefault<IntHasher>>;
use std::sync::atomic::{AtomicUsize, Ordering};

fn number(b: &[u8], p: &mut usize) -> u32 {
    let mut x = 0u32;
    while *p < b.len() && b[*p] > b' ' { x = x * 10 + (b[*p] - b'0') as u32; *p += 1; }
    while *p < b.len() && b[*p] <= b' ' { *p += 1; }
    x
}
struct Graph { offsets: Vec<usize>, edges: Vec<(u32,u32)> }
fn make_graph(n: usize, es: &[(u32,u32,u32)], reverse: bool) -> Graph {
    let mut offsets = vec![0usize; n+1];
    for &(u,v,_) in es { offsets[if reverse { v } else { u } as usize + 1] += 1; }
    for i in 1..=n { offsets[i] += offsets[i-1]; }
    let mut next = offsets.clone();
    let mut edges = vec![(0,0); es.len()];
    for &(u,v,w) in es {
        let (u,v) = if reverse {(v,u)} else {(u,v)};
        edges[next[u as usize]] = (v,w);
        next[u as usize] += 1;
    }
    Graph {offsets,edges}
}
struct Search { d: [Dist;2] }
impl Search {
    fn new(_n:usize) -> Self { Self {d:[Dist::default(),Dist::default()]} }
    fn run(&mut self, gs: [&Graph;2], s:usize, t:usize) -> Option<u64> {
        if s==t { return Some(0); }
        if gs[0].offsets[s]==gs[0].offsets[s+1] || gs[1].offsets[t]==gs[1].offsets[t+1] { return None; }
        self.d[0].clear(); self.d[1].clear();
        let mut q = [BinaryHeap::new(), BinaryHeap::new()];
        for (k,v) in [s,t].into_iter().enumerate() { self.d[k].insert(v,0); q[k].push(Reverse((0u64,v))); }
        let mut best = u64::MAX;
        loop {
            for (k,heap) in q.iter_mut().enumerate() {
                while let Some(&Reverse((d,v)))=heap.peek() {
                    if self.d[k].get(&v)==Some(&d) {break;} heap.pop();
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
                if self.d[k].get(&to).map_or(true, |&old| nd<old) {
                    self.d[k].insert(to,nd); q[k].push(Reverse((nd,to)));
                    if let Some(&opposite)=self.d[1-k].get(&to) { best=best.min(nd+opposite); }
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
    for _ in 0..m { es.push((number(&b,&mut p),number(&b,&mut p),number(&b,&mut p))); }
    drop(b);
    let forward=make_graph(n,&es,false); let backward=make_graph(n,&es,true); drop(es);
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

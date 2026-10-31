from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'baseline.rs').read_text()
anchor='impl Csr {\n'
assert s.count(anchor)==1
methods='''impl Csr {
    #[inline(always)]
    fn node_at(&self, i: usize) -> u32 {
        if self.compact.is_empty() { self.adj[i] as u32 } else { self.compact[i] & ((1 << 21) - 1) }
    }
'''
s=s.replace(anchor,methods)
anchor='struct Search32 { dist:Vec<[u32;2]>, touched:Vec<u32>, heaps:[FastHeap;2] }'
assert s.count(anchor)==1
hint='''#[inline(always)]
fn hint_slot(base: *const [u32; 2], vertex: u32) {
    let p = base.wrapping_add(vertex as usize).cast::<u8>();
    #[cfg(target_arch = "x86_64")]
    unsafe { std::arch::x86_64::_mm_prefetch(p.cast(), std::arch::x86_64::_MM_HINT_T0); }
    #[cfg(target_arch = "aarch64")]
    unsafe { std::arch::asm!("prfm pldl1keep, [{p}]", p=in(reg) p, options(readonly, nostack, preserves_flags)); }
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    let _ = p;
}
'''
s=s.replace(anchor,hint+anchor)
old='''                for (v,w) in graphs[side].edges(u) {
                    let nd=d+w;'''
assert s.count(old)==1
for mode in ('control','ahead1','ahead2','whole'):
 if mode=='control': prefix=''
 elif mode=='whole': prefix='''                let graph = graphs[side];
                let row_start = graph.first[u as usize] as usize;
                let row_end = graph.first[u as usize + 1] as usize;
                for pos in row_start..row_end { hint_slot(self.dist.as_ptr(), graph.node_at(pos)); }
'''
 else:
  num=int(mode[-1]);prefix='''                let graph = graphs[side];
                let row_start = graph.first[u as usize] as usize;
                let row_end = graph.first[u as usize + 1] as usize;
'''
 if mode.startswith('ahead'):
  loop=f'''                for (offset,(v,w)) in graphs[side].edges(u).enumerate() {{
                    let lookahead = row_start + offset + {num};
                    if lookahead < row_end {{ hint_slot(self.dist.as_ptr(), graph.node_at(lookahead)); }}
                    let nd=d+w;'''
 else: loop='''                for (v,w) in graphs[side].edges(u) {
                    let nd=d+w;'''
 candidate=s.replace(old,prefix+loop)
 (p/(mode+'.rs')).write_text(candidate)

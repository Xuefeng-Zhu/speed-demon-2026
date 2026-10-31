from pathlib import Path
p=Path(__file__).parent
src=(p/'baseline.rs').read_text()
assert src.count('            for (v, w) in graphs[side].edges(u) {')==1
prefetch='''#[inline(always)]
fn prefetch_slot(base: *const [u64; 2], index: usize) {
    let ptr = base.wrapping_add(index).cast::<u8>();
    #[cfg(target_arch = "x86_64")]
    unsafe { std::arch::x86_64::_mm_prefetch(ptr.cast(), std::arch::x86_64::_MM_HINT_T0); }
    #[cfg(target_arch = "aarch64")]
    unsafe { std::arch::asm!("prfm pldl1keep, [{p}]", p=in(reg) ptr, options(readonly, nostack, preserves_flags)); }
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    let _ = ptr;
}

'''
# Reuse the exact packed/wide decoding logic from the selected implementation.
helper='''    #[inline(always)]
    fn edge_at(&self, i: usize) -> (u32, u64) {
        if self.compact.is_empty() {
            let e = self.adj[i]; (e as u32, e >> 32)
        } else {
            let e = self.compact[i];
            let tag = e >> 21;
            (e & ((1 << 21) - 1), if tag == 2047 { self.wide[i] as u64 } else { tag as u64 })
        }
    }
    #[inline(always)]
    fn node_at(&self, i: usize) -> u32 {
        if self.compact.is_empty() { self.adj[i] as u32 } else { self.compact[i] & ((1 << 21) - 1) }
    }
'''
assert src.count('impl Csr {')==1
src=src.replace('impl Csr {','impl Csr {\n'+helper,1)
assert src.count('struct Search {')==1
src=src.replace('struct Search {',prefetch+'struct Search {',1)
needle='            for (v, w) in graphs[side].edges(u) {'
for kind in ['control','ahead1','ahead2','ahead4','whole']:
 if kind=='whole':
  hint='''            for pos in begin..end {
                prefetch_slot(self.dist.as_ptr(), graph.node_at(pos) as usize);
            }
'''
 elif kind=='control':
  hint=''
 else:
  n=int(kind[-1]);hint=f'                if pos + {n} < end {{ prefetch_slot(self.dist.as_ptr(), graph.node_at(pos + {n}) as usize); }}\n'
 prefix='''            let graph = graphs[side];
            let begin = graph.first[u as usize] as usize;
            let end = graph.first[u as usize + 1] as usize;
'''
 if kind=='whole': body=prefix+hint+'            for pos in begin..end {\n                let (v, w) = graph.edge_at(pos);'
 else: body=prefix+'            for pos in begin..end {\n'+hint+'                let (v, w) = graph.edge_at(pos);'
 (p/f'{kind}.rs').write_text(src.replace(needle,body,1))

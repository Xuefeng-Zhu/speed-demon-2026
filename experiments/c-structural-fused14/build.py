from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'baseline.rs').read_text()
marker='/// Compact event uses a byte offset and group; u16::MAX marks a long name.'
code=r'''
/// Experimental quote-parity structural scanner; starts and ends at record boundaries.
struct StructuralCursor {
    b: &'static [u8], next: usize, end: usize, base: usize, len: usize,
    pending: u32, quotes: u32, from: usize, carry: bool, field_start: usize,
    prior_quotes: usize,
}
impl StructuralCursor {
    fn new(b: &'static [u8], start: usize, end: usize) -> Self {
        Self { b, next:start, end, base:start, len:0, pending:0, quotes:0,
               from:0, carry:false, field_start:start, prior_quotes:0 }
    }
    #[inline(always)]
    fn load(&mut self) -> bool {
        if self.next == self.end { return false; }
        self.base=self.next; self.len=(self.end-self.next).min(32);
        let slice=&self.b[self.base..self.base+self.len];
        #[cfg(all(target_arch="x86_64",target_feature="avx2"))]
        let (q,d,next_carry)=if self.len==32 { unsafe { structural_avx2(slice,self.carry) } } else { structural_scalar(slice,self.carry) };
        #[cfg(not(all(target_arch="x86_64",target_feature="avx2")))]
        let (q,d,next_carry)=structural_scalar(slice,self.carry);
        self.quotes=q; self.pending=d; self.carry=next_carry;
        self.from=0; self.next+=self.len; true
    }
    #[inline(always)]
    fn qcount(&self, from:usize, to:usize)->usize {
        let m=((1u64<<to)-1)^((1u64<<from)-1);
        (self.quotes & m as u32).count_ones() as usize
    }
    #[inline(always)]
    fn span(&mut self) -> (usize,usize,usize) {
        loop {
            if self.pending!=0 {
                let at=self.pending.trailing_zeros() as usize;
                self.pending &= self.pending-1;
                let q=self.prior_quotes+self.qcount(self.from,at);
                self.prior_quotes=0; self.from=at+1;
                let end=self.base+at; let start=self.field_start; self.field_start=end+1;
                return (start,end,q);
            }
            self.prior_quotes+=self.qcount(self.from,self.len);
            if !self.load() { panic!("incomplete record in chunk"); }
        }
    }
    #[inline(always)]
    fn done(&self)->bool { self.field_start>=self.end }
}
#[inline(always)]
fn structural_scalar(s:&[u8],mut inside:bool)->(u32,u32,bool) {
    let (mut q,mut d)=(0u32,0u32);
    for (i,&c) in s.iter().enumerate() {
        if c==b'"' {q|=1<<i;inside=!inside;}
        if !inside && (c==b',' || c==b'\n') { d|=1<<i; }
    }
    (q,d,inside)
}
#[cfg(all(target_arch="x86_64",target_feature="avx2"))]
#[inline(always)]
unsafe fn structural_avx2(s:&[u8],carry:bool)->(u32,u32,bool) {
    use std::arch::x86_64::*;
    debug_assert_eq!(s.len(),32);
    let v=unsafe {_mm256_loadu_si256(s.as_ptr().cast())};
    let q=unsafe {_mm256_movemask_epi8(_mm256_cmpeq_epi8(v,_mm256_set1_epi8(b'"' as i8)))} as u32;
    let d=unsafe {_mm256_movemask_epi8(_mm256_or_si256(_mm256_cmpeq_epi8(v,_mm256_set1_epi8(b',' as i8)),_mm256_cmpeq_epi8(v,_mm256_set1_epi8(b'\n' as i8))))} as u32;
    let mut inside=q; inside^=inside<<1; inside^=inside<<2; inside^=inside<<4;
    inside^=inside<<8; inside^=inside<<16; if carry {inside=!inside;}
    (q,d & !inside,carry ^ (q.count_ones() & 1 != 0))
}
/// Strip only valid outer quotes and count doubled quote pairs.
#[inline(always)]
fn structural_text(b:&'static [u8],s:usize,e:usize,q:usize)->(&'static [u8],i64) {
    if b[s]==b'"' {
        debug_assert!(q>=2 && q%2==0 && e>s+1 && b[e-1]==b'"');
        let raw=&b[s+1..e-1]; (raw,(raw.len()-(q-2)/2) as i64)
    } else { debug_assert_eq!(q,0); (&b[s..e],(e-s) as i64) }
}
'''
assert s.count(marker)==1;s=s.replace(marker,code+'\n'+marker)
start=s.index('            let (mut p0, end0) = (bound2(t), bound2(t + 1));')
end=s.index('            (agg, bins)\n',start)
new=r'''            let (mut c0,mut c1)=(StructuralCursor::new(recs,bound2(t),bound2(t+1)),StructuralCursor::new(recs,bound2(t+n),bound2(t+n+1)));
            let mut agg = vec![EMPTY; unmatched + 1];
            let mut bins = vec![Vec::<Event>::new(); parts];
            while !c0.done() && !c1.done() {
                let (s0,e0,_) = c0.span(); let (s1,e1,_) = c1.span();
                let mut p0=s0+3*recs[s0..].starts_with(b"\xEF\xBB\xBF") as usize;
                let mut p1=s1+3*recs[s1..].starts_with(b"\xEF\xBB\xBF") as usize;
                let id0=positive_fast(recs,&mut p0); let id1=positive_fast(recs,&mut p1);
                debug_assert_eq!(p0,e0+1); debug_assert_eq!(p1,e1+1);
                let (s0,e0,q0)=c0.span(); let (s1,e1,q1)=c1.span();
                let (name0,name_len0)=structural_text(recs,s0,e0,q0); let (name1,name_len1)=structural_text(recs,s1,e1,q1);
                let h0=name_hash(name0); let h1=name_hash(name1);
                let (s0,e0,q0)=c0.span(); let (s1,e1,q1)=c1.span();
                let (_,note_len0)=structural_text(recs,s0,e0,q0); let (_,note_len1)=structural_text(recs,s1,e1,q1);
                let (mut p0,e0,_)=c0.span(); let (mut p1,e1,_)=c1.span();
                let rid0=positive_fast(recs,&mut p0) as usize; let rid1=positive_fast(recs,&mut p1) as usize;
                debug_assert_eq!(p0,e0+1); debug_assert_eq!(p1,e1+1);
                let g0=unmatched.min(*region.get(rid0).unwrap_or(&u16::MAX) as usize);
                let g1=unmatched.min(*region.get(rid1).unwrap_or(&u16::MAX) as usize);
                let (mut p0,e0,_)=c0.span(); let (mut p1,e1,_)=c1.span();
                let cents0=number(recs,&mut p0); let cents1=number(recs,&mut p1);
                debug_assert_eq!(p0,e0+1); debug_assert_eq!(p1,e1+1);
                for (name,name_len,h,note_len,g,id,cents) in [
                    (name0,name_len0,h0,note_len0,g0,id0,cents0),
                    (name1,name_len1,h1,note_len1,g1,id1,cents1),
                ] {
                    let bucket=((h as u128 * parts as u128)>>64) as usize;
                    let offset=(name.as_ptr() as usize-recs.as_ptr() as usize) as u32;
                    let len=u16::try_from(name.len()).unwrap_or(u16::MAX);
                    bins[bucket].push(Event {offset,len,group:g as u16,hash:h});
                    merge(&mut agg[g],[1,id,cents,cents,cents,0,name_len,note_len]);
                }
            }
            for mut c in [c0,c1] {
                while !c.done() {
                    let (s,e,_)=c.span(); let mut p=s+3*recs[s..].starts_with(b"\xEF\xBB\xBF") as usize;
                    let id=positive_fast(recs,&mut p); debug_assert_eq!(p,e+1);
                    let (s,e,q)=c.span(); let (name,name_len)=structural_text(recs,s,e,q); let h=name_hash(name);
                    let (s,e,q)=c.span(); let (_,note_len)=structural_text(recs,s,e,q);
                    let (mut p,e,_)=c.span(); let rid=positive_fast(recs,&mut p) as usize; debug_assert_eq!(p,e+1);
                    let g=unmatched.min(*region.get(rid).unwrap_or(&u16::MAX) as usize);
                    let (mut p,e,_)=c.span(); let cents=number(recs,&mut p); debug_assert_eq!(p,e+1);
                    let bucket=((h as u128 * parts as u128)>>64) as usize;
                    let offset=(name.as_ptr() as usize-recs.as_ptr() as usize) as u32;
                    let len=u16::try_from(name.len()).unwrap_or(u16::MAX);
                    bins[bucket].push(Event {offset,len,group:g as u16,hash:h});
                    merge(&mut agg[g],[1,id,cents,cents,cents,0,name_len,note_len]);
                }
            }
'''
s=s[:start]+new+s[end:]
(p/'candidate.rs').write_text(s)

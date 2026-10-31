//! Independent prototype: CSV outside-quote structural-byte cursor.
//! No input assumptions about record length; bytes are never read past slice end.

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Structural { pub at: usize, pub byte: u8, pub quotes_since_previous: usize }

#[derive(Clone, Copy, Debug)]
struct Block { quotes: u32, structural: u32, carry: bool }

#[inline]
fn scalar_block(data: &[u8], mut carry: bool) -> Block {
    assert!(data.len() <= 32);
    let (mut quotes,mut structural)=(0u32,0u32);
    for (i,&b) in data.iter().enumerate() {
        if b == b'"' { quotes |= 1u32 << i; carry=!carry; }
        if !carry && matches!(b,b','|b'\r'|b'\n') { structural |= 1u32 << i; }
    }
    Block { quotes,structural,carry }
}

#[cfg(target_arch="x86_64")]
#[target_feature(enable="avx2")]
unsafe fn vector_block(data: &[u8], carry: bool) -> Block {
    use std::arch::x86_64::*;
    assert!(data.len() == 32);
    let b=unsafe {_mm256_loadu_si256(data.as_ptr().cast())};
    let eq=|needle| _mm256_cmpeq_epi8(b,_mm256_set1_epi8(needle));
    let q=_mm256_movemask_epi8(eq(b'"' as i8)) as u32;
    let d=_mm256_movemask_epi8(_mm256_or_si256(_mm256_or_si256(eq(b',' as i8),eq(b'\r' as i8)),eq(b'\n' as i8))) as u32;
    // Inclusive XOR prefix marks positions after an odd number of quotes.
    let mut inside=q;
    inside ^= inside << 1; inside ^= inside << 2; inside ^= inside << 4;
    inside ^= inside << 8; inside ^= inside << 16;
    if carry { inside = !inside; }
    Block {quotes:q,structural:d & !inside,carry:carry ^ (q.count_ones() & 1 != 0)}
}

pub struct Cursor<'a> {
    data: &'a [u8], next_block: usize, base: usize, block_len: usize,
    quote_mask: u32, pending: u32, from: usize, pending_quotes: usize,
    carry: bool, use_avx2: bool,
}
impl<'a> Cursor<'a> {
    /// `prefer_avx2` selects AVX2 only when runtime detection reports support.
    pub fn new(data: &'a [u8], prefer_avx2: bool) -> Self {
        #[cfg(target_arch="x86_64")]
        let use_avx2=prefer_avx2 && std::arch::is_x86_feature_detected!("avx2");
        #[cfg(not(target_arch="x86_64"))]
        let use_avx2={let _=prefer_avx2;false};
        Self {data,next_block:0,base:0,block_len:0,quote_mask:0,pending:0,from:0,pending_quotes:0,carry:false,use_avx2}
    }
    fn load(&mut self) -> bool {
        if self.next_block == self.data.len() {return false;}
        self.base=self.next_block;
        self.block_len=(self.data.len()-self.base).min(32);
        let data=&self.data[self.base..self.base+self.block_len];
        #[cfg(target_arch="x86_64")]
        let block=if self.use_avx2 && self.block_len == 32 { unsafe {vector_block(data,self.carry)} } else {scalar_block(data,self.carry)};
        #[cfg(not(target_arch="x86_64"))]
        let block={let _=self.use_avx2;scalar_block(data,self.carry)};
        self.quote_mask=block.quotes;self.pending=block.structural;self.carry=block.carry;self.from=0;
        self.next_block += self.block_len;
        true
    }
    fn quotes_between(&self, from: usize, until: usize) -> usize {
        let range=((1u64 << until)-1) ^ ((1u64 << from)-1);
        (self.quote_mask & range as u32).count_ones() as usize
    }
    pub fn next_structural(&mut self) -> Option<Structural> {
        loop {
            if self.pending != 0 {
                let at=self.pending.trailing_zeros() as usize;
                self.pending &= self.pending-1;
                self.pending_quotes += self.quotes_between(self.from,at);
                self.from=at+1;
                let quotes_since_previous=std::mem::take(&mut self.pending_quotes);
                return Some(Structural{at:self.base+at,byte:self.data[self.base+at],quotes_since_previous});
            }
            self.pending_quotes += self.quotes_between(self.from,self.block_len);
            if !self.load() { return None; }
        }
    }
}

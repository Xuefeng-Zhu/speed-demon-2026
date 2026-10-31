#[cfg(test)]
mod structural_tests {
    use super::*;
    fn rng(x:&mut u64)->u64 { *x ^= *x<<13; *x ^= *x>>7; *x ^= *x<<17; *x }
    #[test]
    fn blocks_and_spans_match_independent_scalar_oracle() {
        let mut seed=0x1938a4bc12dfe871;
        let alphabet=[b'"',b',',b'\n',b'\r',b'A',b' ',b'0'];
        for len in 0..=256 {
            for _ in 0..1200 {
                let data:Vec<u8>=(0..len).map(|_|alphabet[(rng(&mut seed)%alphabet.len() as u64) as usize]).collect();
                let mut inside=false; let mut old=0usize; let mut q=0usize; let mut expect=Vec::new();
                for (i,&b) in data.iter().enumerate() {
                    if b==b'"' {inside=!inside;q+=1;}
                    else if !inside && (b==b',' || b==b'\n') { expect.push((old,i,q)); old=i+1;q=0; }
                }
                let data: &'static [u8]=Box::leak(data.into_boxed_slice());
                let mut c=StructuralCursor::new(data,0,len);
                for e in expect {assert_eq!(c.span(),e,"len={len}");}
                #[cfg(all(target_arch="x86_64",target_feature="avx2"))]
                if len>=32 {for carry in [false,true] {for off in 0..=len-32 {
                    assert_eq!(unsafe{structural_avx2(&data[off..off+32],carry)},structural_scalar(&data[off..off+32],carry));
                }}}
            }
        }
    }
    #[test]
    fn valid_field_quote_counts_match_existing_parser() {
        let mut seed=0x92de30bc0174a551;
        for len in 0..=512 {
            for _ in 0..32 {
                let mut raw=Vec::new();
                for _ in 0..len {raw.push([b'A',b' ',b',',b'\n',b'"'][(rng(&mut seed)%5) as usize]);}
                let mut csv=vec![b'"']; for &x in &raw {csv.push(x);if x==b'"'{csv.push(x);}} csv.extend_from_slice(b"\",x\n");
                let b:&'static [u8]=Box::leak(csv.into_boxed_slice());let mut c=StructuralCursor::new(b,0,b.len());let (s,e,q)=c.span();
                let (key,n)=structural_text(b,s,e,q);let mut pos=0;let (expected,n0)=field(b,&mut pos);
                assert_eq!(key,expected);assert_eq!(n,n0);assert_eq!(n as usize,raw.len());
            }
        }
    }
}

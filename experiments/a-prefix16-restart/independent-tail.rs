#[cfg(test)]
mod independent {
    use super::*;
    fn expected(bytes: &[u8]) -> u64 {
        let mut h = 0u64;
        let mut chunks = bytes.chunks_exact(8);
        for c in &mut chunks { h = (h ^ u64::from_le_bytes(c.try_into().unwrap())).wrapping_mul(MIX); }
        let rem=chunks.remainder(); let mut tail=[0u8;8]; tail[..rem.len()].copy_from_slice(rem);
        (h ^ u64::from_le_bytes(tail) ^ rem.len() as u64).wrapping_mul(MIX)
    }
    #[test]
    fn canonical_hash_boundaries_and_tail() {
        let alphabet=b"/ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.{}:";
        for len in 1..=125usize { for offset in 0..64usize { for seed in 0..11usize {
            let mut d=vec![b'~';offset]; let s=d.len();d.push(b'/');
            for i in 1..len {d.push(alphabet[(i*13+seed*17+len)%alphabet.len()]);}
            let e=d.len();let exp=expected(&d[s..e]); d.extend_from_slice(b" 200 0\n"); d.resize(d.len()+4096,0);
            assert_eq!(original_hash(&d,s,e),exp,"len={len} offset={offset} seed={seed}");
        }}}
    }
    fn logs(names: &[String]) -> (Vec<u8>,usize) {
        let mut d=Vec::new();
        for (i,n) in names.iter().enumerate() {
            d.extend_from_slice(format!("2026-10-30T18:00:00.000000Z GET {} {} {}\n",n,if i%2==0 {200}else{500},i).as_bytes());
        }
        let end=d.len();d.resize(end+4096,0);(d,end)
    }
    #[test]
    fn collision_abort_then_exact_restart() {
        let names:Vec<String>=(0..100).map(|i|format!("/abcdefghijklmno/{i:04}")).collect();
        assert!(names.iter().all(|s|s.len()==21 && &s.as_bytes()[..16]==b"/abcdefghijklmno"));
        let (d,end)=logs(&names);
        assert!(parse_impl::<true>(&d,0,end).is_none(),"collision threshold must force the restart");
        let resumed=parse(&d,0,end);let exact=parse_impl::<false>(&d,0,end).unwrap();
        assert_eq!(resumed.table.names,exact.table.names);assert_eq!(resumed.hours,exact.hours);
        assert_eq!(resumed.table.names.len(),names.len());
    }
    #[test]
    fn rehash_growth_preserves_ids() {
        let mut d=Vec::new();let mut ranges=Vec::new();
        for i in 0..2100 {let s=d.len();d.extend_from_slice(format!("/x{i:04}").as_bytes());let e=d.len();ranges.push((s,e));d.extend_from_slice(b"        ");}
        d.resize(d.len()+4096,0);let mut t=Table::default();
        for (i,&(s,e)) in ranges.iter().enumerate() {assert_eq!(t.find::<true>(&d,(i as u64)<<40,s,e),Some(i));}
        assert!(t.slots.len()>4096);
        for (i,&(s,e)) in ranges.iter().enumerate() {assert_eq!(t.find::<true>(&d,(i as u64)<<40,s,e),Some(i));}
    }
    #[test]
    fn shard_normalization_same_endpoint_different_orders() {
        let names=["/a", "/abcdefgh", "/abcdefghijklmnop", "/longer_than_sixteen_bytes"].map(String::from);
        let (d,end)=logs(&names);let c=parse_impl::<true>(&d,0,end).unwrap();
        for &(h,s,e) in &c.table.names { assert_eq!(h,expected(&d[s..e])); }
        let other=[names[3].clone(),names[1].clone(),names[0].clone(),names[2].clone()];
        let (d2,end2)=logs(&other);let c2=parse_impl::<true>(&d2,0,end2).unwrap();
        for &(h,s,e) in &c2.table.names {
            let (_,s1,e1)=c.table.names.iter().copied().find(|(_,a,b)|d[*a..*b]==d2[s..e]).unwrap();
            assert_eq!(h,original_hash(&d,s1,e1));
        }
    }
}

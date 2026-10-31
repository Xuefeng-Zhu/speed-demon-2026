#[cfg(test)] mod prefix_review {
 use super::*;
 fn baseline_hash(d:&[u8],s:usize)->(usize,u64){let(mut e,mut h)=(s,0u64);loop {let w=load(d,e);let k=find_byte(w,b' ');if k<8{return(e+k,(h^(w&((1<<8*k)-1))^k as u64).wrapping_mul(MIX));}h=(h^w).wrapping_mul(MIX);e+=8;}}
 #[test] fn canonical_hash_all_lengths_alignments() {
  for len in 1..=125 {for pad in 0..64 {for tail in [b'0',b'5',b'9'] {
   let mut d=vec![b'X';pad]; d.push(b'/');for i in 1..len {d.push(b'a'+(i%26) as u8);}d.extend_from_slice(&[b' ',tail,b'0',b'0',b' ',b'1',b'\n']);d.resize(d.len()+4096,0);
   let(e,h)=baseline_hash(&d,pad);assert_eq!(e,pad+len);assert_eq!(original_hash(&d,pad,e),h,"len={len} pad={pad}");
  }}}
 }
 fn records(count:usize)->Vec<u8>{let mut d=Vec::new();for i in 0..count {d.extend_from_slice(format!("2026-10-30T18:00:00.000000Z GET /abcdefghijklmno{i:04} 200 0\n").as_bytes());}d}
 #[test] fn exact_collision_cutoff_and_restart() {
  let mut a=records(49);let ae=a.len();a.resize(ae+4096,0);assert!(parse_impl::<true>(&a,0,ae).is_some(),"48 collisions are accepted");
  let mut b=records(50);let be=b.len();b.resize(be+4096,0);assert!(parse_impl::<true>(&b,0,be).is_none(),"49th collision forces restart");
  let got=parse(&b,0,be);let strong=parse_impl::<false>(&b,0,be).unwrap();
  assert_eq!(got.table.names,strong.table.names);assert_eq!(got.hours,strong.hours);
 }
 #[test] fn successful_weak_rebuild_keeps_ids() {
  let mut d=records(49);let end=d.len();d.resize(end+4096,0);
  let got=parse_impl::<true>(&d,0,end).unwrap();let strong=parse_impl::<false>(&d,0,end).unwrap();
  assert_eq!(got.table.names,strong.table.names);assert_eq!(got.hours,strong.hours);
 }
}

fn push_num(out: &mut Vec<u8>, mut v: u64) {
    const DIGITS: &[u8; 200] = b"00010203040506070809101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899";
    let mut buf = [0u8; 20];
    let mut pos = buf.len();
    while v >= 100 {
        let q = v / 100;
        let r = (v - q * 100) as usize;
        pos -= 2;
        buf[pos] = DIGITS[2 * r];
        buf[pos + 1] = DIGITS[2 * r + 1];
        v = q;
    }
    if v < 10 { pos -= 1; buf[pos] = b'0' + v as u8; }
    else { pos -= 2; buf[pos] = DIGITS[2 * v as usize]; buf[pos + 1] = DIGITS[2 * v as usize + 1]; }
    out.push(b' ');
    out.extend_from_slice(&buf[pos..]);
}


fn verify(x:u64) {
 let mut actual=b"prefix".to_vec(); push_num(&mut actual,x);
 let expected=format!("prefix {}",x).into_bytes();
 assert_eq!(actual,expected,"mismatch for {x}");
}
fn main() {
 for x in 0..1_000_000 { verify(x); }
 for base in [10_u64,100,1000,10_000,100_000,1_000_000,10_000_000,100_000_000,1_000_000_000,10_000_000_000,100_000_000_000,1_000_000_000_000,10_000_000_000_000,100_000_000_000_000,1_000_000_000_000_000,10_000_000_000_000_000,100_000_000_000_000_000,1_000_000_000_000_000_000,10_000_000_000_000_000_000,u64::MAX] {
   for d in 0..=1000 { if let Some(x)=base.checked_sub(d) {verify(x)} if let Some(x)=base.checked_add(d){verify(x)} }
 }
 let mut x=0xd4b937e93c1f8721_u64;
 for _ in 0..2_000_000 { x ^= x << 13; x ^= x >> 7; x ^= x << 17; verify(x); }
 let numbers=[0,9,10,99,100,101,u32::MAX as u64,u64::MAX,0];
 let mut actual=Vec::new(); for x in numbers {push_num(&mut actual,x);}
 let expected=numbers.iter().map(|n|format!(" {n}")).collect::<String>().into_bytes();assert_eq!(actual,expected);
 println!("PASS 1,000,000 small, 2,000,000 pseudorandom u64, boundary neighborhoods and concatenation");
}

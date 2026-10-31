#[inline]
fn token_len(data: &[u8], start: usize, tok: &[bool; 256]) -> usize {
    const H: u64 = 0x8080_8080_8080_8080;
    const LOA: u64 = 0x6161_6161_6161_6161;
    const HIA: u64 = 0x7b7b_7b7b_7b7b_7b7b;
    const LOD: u64 = 0x3030_3030_3030_3030;
    const HID: u64 = 0x3a3a_3a3a_3a3a_3a3a;
    let mut i = start;
    while i + 8 <= data.len() {
        let x = u64::from_le_bytes(data[i..i + 8].try_into().unwrap());
        let y = x | 0x2020_2020_2020_2020;
        let a = ((y | H).wrapping_sub(LOA) & !((y | H).wrapping_sub(HIA))) & H;
        let d = ((x | H).wrapping_sub(LOD) & !((x | H).wrapping_sub(HID))) & H;
        let invalid = !((a | d) & !x) & H;
        if invalid != 0 { return i - start + (invalid.trailing_zeros() as usize / 8); }
        i += 8;
    }
    while i < data.len() && tok[data[i] as usize] { i += 1; }
    i - start
}

fn main(){ let tok:[bool;256]=std::array::from_fn(|b| (b as u8).is_ascii_alphanumeric()); for prefix in 0..16 { for position in 0..32 { for byte in 0..=255u16 { let mut v=vec![b'a';64+prefix]; v[prefix+position]=byte as u8; v.push(b' '); let got=token_len(&v,prefix,&tok);let exp=v[prefix..].iter().take_while(|&&b|tok[b as usize]).count();assert_eq!(got,exp,"prefix={prefix} pos={position} byte={byte}"); } } } println!("PASS 131072 byte/lane combinations"); }
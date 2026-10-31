fn main(){
 let alphabet=b"0123456789abcdefghijklmnopqrstuvwxyz";let mut seen=vec![0u8;1<<21];let mut cases=0usize;
 for n in 1..=4 {let mut total=1usize;for _ in 0..n {total*=36;}
  for mut code in 0..total {let mut raw=0u64;let mut upper=0u64;let mut expected=0usize;
   for pos in 0..n {let c=alphabet[code%36];code/=36;raw|=(c as u64)<<(8*pos);let u=if c.is_ascii_lowercase(){c-32}else{c};upper|=(u as u64)<<(8*pos);let digit=if c.is_ascii_digit(){(c-b'0'+16)as usize}else{(c-b'a'+33)as usize};expected|=digit<<(6*pos);}
   let idx=direct_index(raw);assert_eq!(idx,expected);assert!(idx<1<<24);assert_ne!(idx,0);
   let normalized=(upper|0x2020_2020_2020_2020u64)&((1u64<<(8*n))-1);
   assert_eq!(idx,direct_index(normalized));
   let (byte,bit)=(idx>>3,1u8<<(idx&7));assert_eq!(seen[byte]&bit,0,"collision at {idx}");seen[byte]|=bit;cases+=1;
  }
 }
 assert_eq!(direct_index(0),0);
 println!("PASS {cases} unique 1-4-byte tokens and uppercase equivalents; zero remains padding");
}

//! Platform-independent semantic model of x86 PMADDUBSW/PMADDWD latency decoding.
fn main() {
    let mut chars=[b'0';8];let mut count=0u64;
    for n in 0..10_000_000u32 {
        let mut x=n; let mut k=0; let mut rev=[0u8;8];
        loop {rev[k]=(x%10) as u8+b'0';k+=1;x/=10;if x==0{break}}
        chars.fill(0xa5);
        for i in 0..k {chars[i]=rev[k-1-i]}
        let word=u64::from_le_bytes(chars);
        let v=(word ^ 0x3030_3030_3030_3030) << (64-8*k);
        let b=v.to_le_bytes();
        let mut pairs=[0u16;4];for i in 0..4 {pairs[i]=u16::from(b[2*i])*10+u16::from(b[2*i+1]); assert!(pairs[i]<=99);}
        let q0=u32::from(pairs[0])*100+u32::from(pairs[1]);
        let q1=u32::from(pairs[2])*100+u32::from(pairs[3]);
        assert_eq!(q0*10_000+q1,n,"{n}");count+=1;
    }
    println!("PASS {count} PMADDUBSW/PMADDWD semantic cases");
}

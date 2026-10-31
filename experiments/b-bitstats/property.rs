fn candidate(first:u32,r:&[u64],top:&mut Vec<u32>)->(u32,u32,u64){
        let start = top.len() as u32;
        let (mut count, mut sum) = (0u32, 0u64);
        for (w, &word) in r.iter().enumerate() {
            if word == 0 { continue; }
            let n = word.count_ones();
            let base = first + w as u32 * 64;
            count += n;
            sum += u64::from(base) * u64::from(n);
            let mut bits = word;
            if n <= 8 {
                while bits != 0 {
                    let pos = bits.trailing_zeros();
                    sum += u64::from(pos);
                    if top.len() - (start as usize) < 10 { top.push(base + pos); }
                    bits &= bits - 1;
                }
            } else {
                sum += u64::from((word & 0xaaaaaaaaaaaaaaaa).count_ones());
                sum += u64::from((word & 0xcccccccccccccccc).count_ones()) * 2;
                sum += u64::from((word & 0xf0f0f0f0f0f0f0f0).count_ones()) * 4;
                sum += u64::from((word & 0xff00ff00ff00ff00).count_ones()) * 8;
                sum += u64::from((word & 0xffff0000ffff0000).count_ones()) * 16;
                sum += u64::from((word & 0xffffffff00000000).count_ones()) * 32;
                while bits != 0 && top.len() - (start as usize) < 10 {
                    let pos = bits.trailing_zeros();
                    top.push(base + pos);
                    bits &= bits - 1;
                }
            }
        }
        (count, start, sum)
}
fn reference(first:u32,r:&[u64],top:&mut Vec<u32>)->(u32,u32,u64) {
 let start=top.len() as u32; let mut n=0u32; let mut sum=0u64;
 for (w,&word) in r.iter().enumerate() { for bit in 0..64 {if word & (1u64<<bit) != 0 {let d=first+(w as u32)*64+bit; if n<10 {top.push(d)}; n+=1;sum+=u64::from(d);}}}
 (n,start,sum)
}
fn check(first:u32, r:&[u64]) { let mut a=vec![999,998,997,996,995]; let mut b=a.clone(); let x=candidate(first,r,&mut a); let y=reference(first,r,&mut b); assert_eq!((x,a),(y,b),"first={first} r={r:?}"); }
#[test] fn exhaustive_masks_and_random_words() {
 for bit in 0..64 {check(0,&[1u64<<bit]);check(200_000,&[1u64<<bit]);}
 for mask in 0u64..65536 {for shift in [0,16,32,48] {check(0,&[mask<<shift]);}}
 let fixed=[0,1,0xff,0x1ff,0x1ff00,0xffffffffffffffff,0xaaaaaaaaaaaaaaaa,0x5555555555555555,0x8000000000000001];
 for &x in &fixed {for &y in &fixed {check(147_111,&[x,y]);}}
 let mut state=0x123456789abcdef0u64;
 for i in 0..100_000 {let len=i%23;let mut a=Vec::new();for _ in 0..len {state^=state<<13;state^=state>>7;state^=state<<17;a.push(state);}check((i%200_000) as u32,&a);}
}

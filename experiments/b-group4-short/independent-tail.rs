fn check(n: usize) -> usize {
    let mut p = Plan { slots: vec![MISS; 1 << 14], ..Default::default() };
    let mut terms = Vec::new();
    for i in 0..n {
        let token = format!("{i:08x}");
        let id = p.intern(token.as_bytes(), 1);
        assert_eq!(id as usize,i);
        terms.push((token, id));
    }
    for (token,id) in [("a", n as u32),("ab",n as u32+1),("abc",n as u32+2),("abcd",n as u32+3),("abcde",n as u32+4),("abcdef",n as u32+5),("abcdefg",n as u32+6),("abcdefgh",n as u32+7),("abcdefghi",n as u32+8)] {
        let actual = p.intern(token.as_bytes(),1);
        assert_eq!(actual,id);
        terms.push((token.to_string(), actual));
    }
    p.build_short();
    for g in &p.short_groups { assert_eq!((g as *const ShortGroup as usize) % 64,0); assert_eq!((g.keys.as_ptr() as usize) % 32,0); }
    let mut checks=0;
    for (term,id) in &terms {
        for pad in 0..32 {
            for tail in ["", "a", "1", "/////////", ",,x"] {
                let text = format!("{}{term}{tail}", "/".repeat(pad));
                let actual=p.lookup_token(text.as_bytes(),pad,term.len());
                assert_eq!(actual,*id,"{term:?}, pad {pad}, tail {tail:?}"); checks+=1;
            }
        }
    }
    for token in ["g","h","i","j","0123456", "87654321", "zzzzzzzz", "000000001"] {
        if terms.iter().any(|(v,_)| v==token) {continue}
        let id=p.lookup_token(token.as_bytes(),0,token.len());
        assert_eq!(id,MISS,"absent {token:?}");checks+=1;
    }
    checks
}
fn main() {
    let mut p=Plan { slots: vec![MISS;1], ..Default::default() };
    p.build_short();
    for b in ["a","0","abcdefg","abcdefgh"] {assert_eq!(p.lookup_token(b.as_bytes(),0,b.len()),MISS);}
    let mut total=4;
    for n in [0,1,2,3,4,5,7,8,9,15,16,17,31,32,33,63,64,65,127,128,129,1024] { total+=check(n); }
    println!("PASS {total} exact/absent key, alignment and growth checks");
}

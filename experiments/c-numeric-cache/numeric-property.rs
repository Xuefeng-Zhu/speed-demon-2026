fn number(b: &[u8], p: &mut usize) -> i64 {
    let neg = b[*p] == b'-';
    *p += neg as usize;
    let mut v: i64 = 0;
    while b[*p].is_ascii_digit() {
        v = v * 10 + i64::from(b[*p] - b'0');
        *p += 1;
    }
    if b[*p] == b'.' {
        v = v * 100 + i64::from(b[*p + 1] - b'0') * 10 + i64::from(b[*p + 2] - b'0');
        *p += 3;
    }
    *p += 1 + (b[*p] == b'\r') as usize;
    if neg { -v } else { v }
}

fn main() {
 for value in -99999i64..=9999999 {
   let sign = if value < 0 {"-"} else {""}; let x = value.unsigned_abs();
   let s = format!("{sign}{}.{:02}\r\n", x / 100, x % 100); let mut p=0;
   let got=number(s.as_bytes(), &mut p); assert_eq!(got,value); assert_eq!(p,s.len());
 }
 for n in [0, 1, 9, 10, 99, 100, 999, 1000, 9999999, 3100000, i32::MAX as i64] {
   for delimiter in [",", "\n", "\r\n"] { let s=format!("{n}{delimiter}"); let mut p=0; assert_eq!(number(s.as_bytes(), &mut p),n); assert_eq!(p,s.len()); }
 }
 println!("PASS exact cents and integer delimiters");
}

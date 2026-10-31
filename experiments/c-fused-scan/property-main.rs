fn test_num(s: &str, expected: i64) {
 let mut a=0; let mut b=0;
 let x=old_number(s.as_bytes(), &mut a);let y=new_number(s.as_bytes(),&mut b);
 assert_eq!((x,a),(expected,s.len()),"old {s:?}");assert_eq!((y,b),(expected,s.len()),"new {s:?}");
}
fn test_field(v: &[u8]) {
 let mut encoded=Vec::with_capacity(v.len()*2+8);encoded.push(b'"');
 for &c in v { encoded.push(c);if c==b'"'{encoded.push(c);} }
 encoded.extend_from_slice(b"\",tail"); let data: &'static [u8]=Box::leak(encoded.into_boxed_slice());
 let mut a=0;let mut b=0;let (x,xn)=old_field(data,&mut a);let (y,yn)=new_field(data,&mut b);
 assert_eq!(x,y);assert_eq!(xn,v.len() as i64);assert_eq!(yn,v.len() as i64);assert_eq!(a,b);assert_eq!(data[a..],*b"tail");
}
fn main() {
 let mut n=0u64;
 for value in -99999i64..=9999999 {
  if value==0 {continue}
  let a=value.unsigned_abs();let sign=if value<0{"-"}else{""};let num=format!("{sign}{}.{:02}",a/100,a%100);
  for d in ["\n", "\r\n"] {test_num(&(num.clone()+d),value); n+=1;}
 }
 for value in [0i64,1,9,10,99,100,999,1000,999999,9999999,39999999] {
  for d in [",", "\n", "\r\n"] {test_num(&(value.to_string()+d),value); n+=1;}
 }
 for d in ["\n","\r\n"] {test_num(&("0.00".to_owned()+d),0);}
 let alphabet=[b'a',b' ',b',',b'"',b'\n'];let mut field_count=0;
 for len in 0..=6u32 {for mut i in 0..5usize.pow(len) {let mut v=Vec::new();for _ in 0..len {v.push(alphabet[i%5]);i/=5;}test_field(&v);field_count+=1;}}
 for len in [7,8,15,16,31,32,63,64,65,4095,4096,4097,131071] { let mut v=vec![b'a';len];for j in (0..len).step_by(7){v[j]=b'"';}test_field(&v);field_count+=1; }
 for s in [b",tail".as_slice(),b"plain,tail".as_slice(),b"123,tail".as_slice()] {let data: &'static [u8]=Box::leak(s.to_vec().into_boxed_slice());let(mut a,mut b)=(0,0);let(x,xn)=old_field(data,&mut a);let(y,yn)=new_field(data,&mut b);assert_eq!((x,xn,a),(y,yn,b));field_count+=1;}
 println!("PASS {n} numeric cases and {field_count} field cases");
}

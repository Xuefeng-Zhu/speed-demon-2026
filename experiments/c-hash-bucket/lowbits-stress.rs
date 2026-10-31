use std::collections::HashMap;
use std::hash::{BuildHasherDefault,Hasher};
use std::time::Instant;
#[derive(Default)] struct Identity(u64);
impl Hasher for Identity {fn write(&mut self,_:&[u8]){unreachable!()}fn write_u64(&mut self,x:u64){self.0=x;}fn finish(&self)->u64{self.0}}
fn main(){for n in [1000u64,4000,16000,64000]{
 let start=Instant::now();let mut m:HashMap<u64,u64,BuildHasherDefault<Identity>>=HashMap::default();
 for i in 0..n{m.insert(i<<20,i);} let elapsed=start.elapsed();
 let start=Instant::now();let mut m2:HashMap<u64,u64>=HashMap::new();for i in 0..n{m2.insert(i<<20,i);}let salted=start.elapsed();
 assert_eq!(m.len(),n as usize);assert_eq!(m2.len(),n as usize);
 println!("n={n} identity_ms={:.3} salted_ms={:.3}",elapsed.as_secs_f64()*1000.,salted.as_secs_f64()*1000.);
}}

fn check(n:usize)->usize {
 let mut p=Plan{slots:vec![MISS;1<<15],..Default::default()};let mut terms=Vec::new();
 for i in 0..n {let term=format!("z{i:03}");let id=p.intern(term.as_bytes(),1);assert_eq!(id as usize,i);terms.push((term,id));}
 for token in ["a","0","ab","000","abcd","abcde","abcdef","abcdefg","abcdefgh","abcdefghi","abcdefghijklmnopqrstuvwxyz123456"] {let id=p.intern(token.as_bytes(),1);terms.push((token.to_string(),id));}
 p.build_short();assert_eq!(p.short_direct.len(),1<<24);let mut cases=0;
 for (term,id) in &terms {for pad in 0..32 {for tail in ["","a","1",",,", "/////////"] {let data=format!("{}{term}{tail}","/".repeat(pad));assert_eq!(p.lookup_token(data.as_bytes(),pad,term.len()),*id);let uppercase=data.to_ascii_uppercase();assert_eq!(p.lookup_token(uppercase.as_bytes(),pad,term.len()),*id);cases+=2;}}}
 for token in ["g","h","i","j","0123","zzzz","87654321","000000001"] {if terms.iter().any(|(v,_)|v==token){continue}assert_eq!(p.lookup_token(token.as_bytes(),0,token.len()),MISS);cases+=1;}
 cases
}
fn main(){
 let mut p=Plan{slots:vec![MISS;1],..Default::default()};p.build_short();for token in ["a","0","1","abcd","aaaa"] {assert_eq!(p.lookup_token(token.as_bytes(),0,token.len()),MISS);}
 let mut c=5;for n in [0,1,2,3,4,7,8,15,16,31,32,127,128,1000] {c+=check(n)}println!("PASS {c} Plan lookup, empty table, absent keys and offsets");
}

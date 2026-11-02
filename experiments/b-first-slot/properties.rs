// Appended to the exact source, whose production main is renamed.
mod independent_probe_properties {
    use super::*;

    fn oracle(table: &[[u64;4]], k: [u64;2], home: usize) -> usize {
        for step in 0..table.len() {
            let i=home.wrapping_add(step) % table.len();
            let entry=table[i];
            if entry[0]==0 || (entry[0]==k[0] && entry[1]==k[1]) { return i; }
        }
        panic!("Invalid full fixture table");
    }
    fn fresh(n: usize) -> Plan {
        let mut p=Plan { filter:vec![0;FILTER/64],role:vec![0],..Default::default() };
        p.grow(n);p
    }
    fn check(p: &Plan,k:[u64;2],h:usize) {
        assert_eq!(p.slot(k,h),oracle(p.keys,k,h),"k={k:?}, h={h}, table={:?}",p.keys);
    }
    pub fn run() {
        let mut cases=0usize;
        for n in [8usize,16,64,256] {
            let mut p=Plan {keys:Box::leak(vec![[0;4];n].into_boxed_slice()),..Default::default()};
            for used in [0,1,n/2,n-1] {
                for start in [0,n/2,n-1] {
                    p.keys.fill([0,0,0xfeed,0]);
                    for j in 0..used {
                        let low=if j%3==0 {77} else {100+j as u64};
                        let high=if j%4==0 {0} else {0xabc0+j as u64};
                        p.keys[(start+j)%n]=[low,high,(j as u64+1)|(3u64<<32),0];
                    }
                    let mut queries=vec![[0,0],[77,0],[77,0xdead],[123456,0],[123456,0xdead]];
                    queries.extend(p.keys.iter().filter(|e|e[0]!=0).map(|e|[e[0],e[1]]));
                    for k in queries {for h in [0,1,n/2,n-1] {check(&p,k,h);cases+=1;}}
                }
            }
        }
        // Actual intern/grow path: unknown ID zero, filter bits updated during
        // insertion, duplicates retain IDs, and >16-byte terms stay in long.
        let mut p=fresh(64);let mut words=Vec::new();let mut ids=Vec::new();
        for i in 0..96000usize {
            let word=format!("q{i:05x}");let id=p.intern(word.as_bytes(),0,word.len(),IN_BOOL);
            assert_eq!(id,i as u32+1);words.push(word);ids.push(id);
        }
        assert!(p.keys.len()>=262144);
        for (word,&id) in words.iter().zip(&ids) {
            assert_eq!(p.intern(word.as_bytes(),0,word.len(),IN_BOOL),id);
            let k=key(word.as_bytes(),0,word.len());let h=Plan::hash(k);
            assert_ne!(p.filter[h%FILTER/64]>>(h%64)&1,0);
            check(&p,k,p.home(k));cases+=1;
        }
        for n in [16,17,31,32] {
            let word="a".repeat(n);let id=p.intern(word.as_bytes(),0,n,0);
            assert_eq!(p.intern(word.as_bytes(),0,n,IN_BOOL),id);
        }
        // Scan the exact staged lookup path, before and after an artificial
        // bijective remap, with packed anchor offsets and unknown short/long.
        let mut p=fresh(64);let mut known=HashMap::new();
        for word in ["a","and","007","abcdefgh","abcdefghz","abcdefghijklmnop","abcdefghijklmnopq","abcdefghijklmnopqrstuvwxzyabcdef"] {
            let id=p.intern(word.as_bytes(),0,word.len(),IN_BOOL);known.insert(word.to_owned(),id);
        }
        p.empty=p.keys.iter().position(|e|e[0]==0).unwrap();
        p.filter.fill(!0); // Valid worst-case false positives: exercise real miss probes.
        p.phr=vec![0;128];
        for remap in [false,true] {
            let translate=|v:u64|if remap {(p.role.len()-1-v as usize) as u64} else {v};
            for entry in p.keys.iter_mut() {
                let id=translate(entry[2]);
                entry[2]=id|if entry[0]!=0 {((id%31+1)<<32)} else {0};
            }
            for value in p.long.values_mut(){let id=translate(*value);*value=id|((id%31+1)<<32);}
            let body=b"0\tA abcdefgh abcdefghy absent and abcdefghijklmnopq 007 abcdefghijklmnopqrstuvwxyzabcdez abcdefghz\n1\tabsentlongabcdefghijklmnopqrstuvw / a 007\n";
            let mut calls=0;
            for_each_doc(body,0,body.len(),&p,|got,anchors| {
                let text=body.split(|&c|c==b'\n').nth(calls).unwrap().splitn(2,|&c|c==b'\t').nth(1).unwrap();
                let mut tokens=Vec::new();let mut current=Vec::new();
                for byte in text.iter().copied().chain([0]) {
                    if byte.is_ascii_alphanumeric(){current.push(byte.to_ascii_lowercase());}
                    else if !current.is_empty(){tokens.push(std::mem::take(&mut current));}
                }
                let mut expected=Vec::new();let mut want_anchors=Vec::new();
                for (j,token) in tokens.iter().enumerate() {
                    let value=if let Some(&old)=known.get(std::str::from_utf8(token).unwrap()) {
                        let id=translate(old as u64);want_anchors.push((j,(id%31) as usize));id
                    } else {translate(0)};
                    expected.push(value as u32);
                }
                assert_eq!(got,expected);assert_eq!(anchors,want_anchors);calls+=1;
            });
            assert_eq!(calls,2);cases+=2;
            // Remove high packed bits so the next artificial remap sees IDs.
            for e in p.keys.iter_mut(){e[2]&=u32::MAX as u64;}
            for v in p.long.values_mut(){*v&=u32::MAX as u64;}
        }
        // Force the optimized scan closure's very first entry to have the
        // same low word but a different high word, rather than only testing
        // that comparison in Plan::slot's unchanged continuation loop.
        let mut p=fresh(64);
        let word="abcdefgh";let id=p.intern(word.as_bytes(),0,word.len(),IN_BOOL);
        let home=p.home(key(word.as_bytes(),0,word.len()));
        let mut absent=String::new();
        for i in 0..10000 {
            let candidate=format!("abcdefgh{i:x}");
            if p.home(key(candidate.as_bytes(),0,candidate.len()))==home {absent=candidate;break;}
        }
        assert!(!absent.is_empty());assert_ne!(key(absent.as_bytes(),0,absent.len())[1],0);
        p.empty=p.keys.iter().position(|e|e[0]==0).unwrap();p.filter.fill(!0);p.phr=vec![0;4];
        p.keys[home][2]=id as u64|(3u64<<32);
        let body=format!("0\t{word} {absent}\n").into_bytes();let mut seen=0;
        for_each_doc(&body,0,body.len(),&p,|tokens,anchors|{assert_eq!(tokens,[id,0]);assert_eq!(anchors,[(0,2)]);seen+=1;});
        assert_eq!(seen,1);cases+=1;
        println!("PROBE_PROPERTY {{\"checks\":{cases},\"growth_distinct_terms\":96000,\"compiled_avx2\":{}}}",cfg!(target_feature="avx2"));
    }
}
fn main(){independent_probe_properties::run();}

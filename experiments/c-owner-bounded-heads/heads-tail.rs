#[cfg(test)]
mod heads_tests {
    use super::*;
    #[test]
    fn clustered_insert_update_promote_and_retain() {
        let mut h=HeadMap::default();
        let salt=h.salt;
        let mut keys=Vec::new();
        for k in 0u64.. { if HeadMap::index(k,salt,15)==0 { keys.push(k); if keys.len()==300 {break} } }
        // Set all keys to one index in a large table so that the 33rd must migrate.
        h.slots=vec![(0,NONE);1024];
        keys.clear();
        for k in 0u64.. { if HeadMap::index(k,salt,1023)==0 { keys.push(k); if keys.len()==80 {break} } }
        for (i,&k) in keys.iter().enumerate() { h.insert(k,i); for (j,&k2) in keys[..=i].iter().enumerate() {assert_eq!(h.get(&k2),Some(j));} }
        assert!(h.fallback.is_some());
        for (i,&k) in keys.iter().enumerate() { h.insert(k,i+200); }
        for (i,&k) in keys.iter().enumerate() { assert_eq!(h.get(&k),Some(i+200)); }
        assert_eq!(h.get(&u64::MAX),None);
    }
    #[test]
    fn random_growth_updates_and_reference() {
        let mut h=HeadMap::default();let mut m=HashMap::new();let mut x=1u64;
        for i in 0..200_000usize { x^=x<<13; x^=x>>7; x^=x<<17; let k=x%23_129; h.insert(k,i); m.insert(k,i); if i%101==0 {assert_eq!(h.get(&k),m.get(&k).copied());} }
        for k in 0..30_000 {assert_eq!(h.get(&k),m.get(&k).copied());}
    }
    #[test]
    fn zero_and_max_key() {
        let mut h=HeadMap::default();for (i,k) in [0,u64::MAX,1,2,3].into_iter().enumerate() {h.insert(k,i);}
        assert_eq!(h.get(&0),Some(0));
    }
}

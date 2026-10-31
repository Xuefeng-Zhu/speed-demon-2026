from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'baseline.rs').read_text()
old='''#[inline]
fn push_word(data: &[u8], start: usize, end: usize, plan: &Plan, tokens: &mut Vec<u32>) {
    let n = end - start;
    tokens.push(if n <= 32 { plan.lookup_token(data, start, n) } else { MISS });
}'''
new='''struct TokenProfile { lengths:[u64;34], hits:[u64;34], probes_hit:[u64;16], probes_miss:[u64;16] }
impl TokenProfile { fn new()->Self { Self {lengths:[0;34],hits:[0;34],probes_hit:[0;16],probes_miss:[0;16]} } }
#[inline]
fn push_word(data: &[u8], start: usize, end: usize, plan: &Plan, tokens: &mut Vec<u32>, stats:&mut TokenProfile) {
    let n = end - start;
    let id = if n <= 32 { plan.lookup_token(data, start, n) } else { MISS };
    let b=n.min(33);stats.lengths[b]+=1;if id!=MISS {stats.hits[b]+=1;}
    if n<=8 {
        let mut pad=[0u8;8]; let src=data.get(start..start+8).unwrap_or_else(||{pad[..n].copy_from_slice(&data[start..start+n]);&pad});
        let x=(u64::from_le_bytes(src.try_into().unwrap())|0x2020_2020_2020_2020)&((1u128<<(n*8))-1) as u64;
        let mask=plan.short_slots.len()-1;let mut i=Plan::short_hash(x)&mask;let mut count=0usize;
        loop { count+=1;let actual=plan.short_slots[i];if actual==MISS || plan.keys[actual as usize].0[0]==x {assert_eq!(actual,id);break;} i=(i+1)&mask; }
        let arr=if id==MISS {&mut stats.probes_miss} else {&mut stats.probes_hit};arr[count.min(15)]+=1;
    }
    tokens.push(id);
}'''
assert s.count(old)==1;s=s.replace(old,new)
s=s.replace('let (mut i, mut done, mut tokens) = (lo, lo, Vec::new());','let (mut i, mut done, mut tokens) = (lo, lo, Vec::new());\n    let mut stats=TokenProfile::new();',1)
s=s.replace('plan, &mut tokens);','plan, &mut tokens, &mut stats);')
needle='''    }
}

enum Query {'''
replace='''    }
    eprintln!("B_TOKEN_PROFILE lo={} hi={} lengths={:?} hits={:?} probes_hit={:?} probes_miss={:?}",lo,hi,stats.lengths,stats.hits,stats.probes_hit,stats.probes_miss);
}

enum Query {'''
assert s.count(needle)==1;s=s.replace(needle,replace)
(p/'profile.rs').write_text(s)

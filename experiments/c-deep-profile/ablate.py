import sys
src, dst, mode = sys.argv[1], sys.argv[2], sys.argv[3]
s=open(src).read()
def rep(a,b):
    global s
    assert s.count(a)==1,a; s=s.replace(a,b)
if mode in ('noroute','nodict','nohash'):
    # keep dictionary probe but do not route events to owners
    rep("""                    let o = &mut out[g % n];
                    o.push((id as u32) << 8 | g as u32);
                    if o.len() == BLOCK {""","""                    let o = &mut out[g % n];
                    agg[g][5] += (id & 1) as i64;
                    if false {""")
if mode in ('nodict','nohash'):
    rep("                        names.id(key, cap),","                        { let k: (u64, usize) = key; k.1 & 1 },")
if mode == 'nohash':
    rep("(ring[r], r) = ((names.key(b, s, e), rid, rec), (r + 1) % RING);","(ring[r], r) = ((((s ^ e) as u64, 0usize), rid, rec), (r + 1) % RING);")
open(dst,'w').write(s)

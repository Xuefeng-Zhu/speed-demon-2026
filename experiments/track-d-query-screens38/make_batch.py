import sys
s=open(sys.argv[1]).read(); n=sys.argv[3]
def rep(a,b):
    global s
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
rep('''    let mut best = if s == t { 0 } else { u64::MAX };
    while let''','''    let mut best = if s == t { 0 } else { u64::MAX };
    let (mut side, mut left) = (0, 0);
    while let''')
rep('''        let side = (sides[0].size > sides[1].size) as usize;''','''        // Expand one side %s times in a row before comparing sizes again.
        if left == 0 {
            (side, left) = ((sides[0].size > sides[1].size) as usize, %s);
        }
        left -= 1;''' % (n,n))
open(sys.argv[2],'w').write(s)

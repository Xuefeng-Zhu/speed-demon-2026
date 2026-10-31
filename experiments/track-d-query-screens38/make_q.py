import sys
s=open(sys.argv[1]).read(); v=sys.argv[3]
def rep(a,b):
    global s
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
if v.startswith('s'):
    rep('const SHIFT: u32 = 6;', f'const SHIFT: u32 = {v[1:]};')
elif v.startswith('pf'):
    f,a=int(v[2]),int(v[3])   # entry offsets from the top for bounds / row
    rep('''        if let Some(&(_, next)) = q.len().checked_sub(2).map(|i| &q[i]) {''',
        f'''        if let Some(&(_, next)) = q.len().checked_sub({f}).map(|i| &q[i]) {{''')
    rep('''        if let Some(&(_, next)) = q.last() {
            let g''', f'''        if let Some(&(_, next)) = q.len().checked_sub({a}).map(|i| &q[i]) {{
            let g''')
open(sys.argv[2],'w').write(s)

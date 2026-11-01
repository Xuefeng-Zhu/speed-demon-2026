import sys
s=open(sys.argv[1]).read()
def rep(a,b):
    global s
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
rep('fn main() {\n','fn main() {\n    let t0 = std::time::Instant::now();\n')
rep('    drop(g);\n','    drop(g);\n    let t1 = t0.elapsed().as_secs_f64() * 1e3;\n')
rep('    let net = Net { graphs, bits, wide };','    let net = Net { graphs, bits, wide };\n    let t2 = t0.elapsed().as_secs_f64() * 1e3;')
rep('    let lines = answers','    eprintln!("MARK relabel {:.2} queries {:.1}", t2 - t1, t0.elapsed().as_secs_f64() * 1e3 - t2);\n    let lines = answers')
for a in sys.argv[3:]:
    old,new=a.split('=>'); rep(old,new)
open(sys.argv[2],'w').write(s)

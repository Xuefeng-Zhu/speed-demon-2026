import sys
s=open(sys.argv[1]).read()
def rep(a,b):
    global s
    assert s.count(a)==1,a[:60]; s=s.replace(a,b)
rep('fn main() {\n','''static PEAK: AtomicU64 = AtomicU64::new(0);
fn anon() -> u64 {
    let st = std::fs::read_to_string("/proc/self/status").unwrap();
    st.lines().find(|l| l.starts_with("RssAnon")).unwrap().split_whitespace().nth(1).unwrap().parse().unwrap()
}
fn main() {
    std::thread::spawn(|| loop {
        PEAK.fetch_max(anon(), Relaxed);
        std::thread::sleep(std::time::Duration::from_micros(200));
    });
''')
rep('    drop(g);\n','    eprintln!("ANON load+renumber peak {} MB", PEAK.swap(0, Relaxed) / 1024);\n    drop(g);\n')
rep('    let net = Net { graphs, bits, wide };','    eprintln!("ANON relabel peak {} MB", PEAK.swap(0, Relaxed) / 1024);\n    let net = Net { graphs, bits, wide };')
rep('    std::process::exit(0);','    eprintln!("ANON query peak {} MB", PEAK.load(Relaxed) / 1024);\n    std::process::exit(0);')
open(sys.argv[2],'w').write(s)

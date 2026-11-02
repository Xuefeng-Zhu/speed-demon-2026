import sys
# Generic TSC instrumentation of for_each_doc passes, CSR and answer for a variant.
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)
rep("use std::fmt::Write as _;\n", "use std::fmt::Write as _;\nfn tsc() -> u64 { unsafe { std::arch::x86_64::_rdtsc() } }\nthread_local! { static ST: std::cell::Cell<[u64; 8]> = const { std::cell::Cell::new([0; 8]) }; }\nfn st(i: usize, d: u64) { ST.with(|c| { let mut a = c.get(); a[i] += d; c.set(a) }) }\n")
# pass boundaries: before each_token call in for_each_doc, after it, before f(&tokens..), after
import re
i0 = s.index("fn for_each_doc(")
i1 = s.index("\n}\n", i0)
body = s[i0:i1]
b2 = body.replace("    while i < hi {\n", "    while i < hi {\n        let t0 = tsc();\n", 1)
k = b2.index("        let long = |")
b2 = b2[:k] + "        let t1 = tsc();\n" + b2[k:]
b2 = b2.replace("        f(&tokens, &anch);\n", "        let t2 = tsc();\n        f(&tokens, &anch);\n        let t3 = tsc();\n        st(0, t1 - t0); st(1, t2 - t1); st(2, t3 - t2);\n", 1)
s = s[:i0] + b2 + s[i1:]
rep('    assert!(doc - first <= 1 << 16, "chunk too large");\n', '    assert!(doc - first <= 1 << 16, "chunk too large");\n    let t5 = tsc();\n')
rep("    hits.dedup(); // a phrase can occur twice in a document\n", "    hits.dedup(); // a phrase can occur twice in a document\n    st(3, tsc() - t5);\n")
import re as _re
_m = _re.search(r"fn answer\((c: &Chunk, plan: &Plan, (\w+): ([^,]+), s: &mut Scratch)\) \{\n", s)
_sig, _a = _m.group(1), _m.group(2)
s = s.replace(_m.group(0), "fn answer(" + _sig + ") {\n    let ta = tsc();\n    answer2(c, plan, " + _a + ", s);\n    st(4, tsc() - ta);\n}\nfn answer2(" + _sig + ") {\n", 1)
rep("fn main() {\n", "fn main() {\n    let t00 = std::time::Instant::now();\n")
# report at end of worker closure: find 'par(nthreads, |_| {' first occurrence (worker), print stats before its closing
if "    par(nthreads, |_| {\n" in s:
    k = s.index("    par(nthreads, |_| {\n"); k2 = s.index("    });\n", k)
else:
    k = s.index("            sc.spawn(|| {\n"); k2 = s.index("            });\n", k)
s = s[:k2] + "        let a = ST.with(|c| c.get());\n        eprintln!(\"scanstat {} {} {} {} {}\", a[0] / 1000000, a[1] / 1000000, a[2] / 1000000, a[3] / 1000000, a[4] / 1000000);\n" + s[k2:]
s = s.replace("    let data = map_file(&format!(\"{data_dir}/docs.txt\"));\n", "    eprintln!(\"parse {:.2}\", t00.elapsed().as_secs_f64() * 1e3);\n    let data = map_file(&format!(\"{data_dir}/docs.txt\"));\n", 1)
s = s.replace("    let next = AtomicUsize::new(0);\n", "    let next = AtomicUsize::new(0);\n    eprintln!(\"start {:.2}\", t00.elapsed().as_secs_f64() * 1e3);\n", 1)
s = s.replace("    std::process::exit(0);", "    eprintln!(\"end {:.2}\", t00.elapsed().as_secs_f64() * 1e3);\n    std::process::exit(0);", 1)
open(dst, 'w').write(s)

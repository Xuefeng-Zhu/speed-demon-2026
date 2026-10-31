import sys
src = open(sys.argv[1]).read()
def rep(a, b, cnt=1):
    global src
    assert src.count(a) == cnt, (a, src.count(a))
    src = src.replace(a, b)
rep("use std::{collections::HashMap, env, fs, thread};", """use std::{collections::HashMap, env, fs, thread};
// PROF: instrumentation (experiments/b-speed3/profile.rs only).
static LOG: std::sync::Mutex<String> = std::sync::Mutex::new(String::new());
static T0: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();
fn ns() -> u64 { T0.get().unwrap().elapsed().as_nanos() as u64 }
fn phase(name: &str) { let t = ns(); writeln!(LOG.lock().unwrap(), "PHASE {name} {t}").unwrap(); }
fn tsc() -> u64 { unsafe { std::arch::x86_64::_rdtsc() } }
thread_local! { static ACC: [std::cell::Cell<u64>; 24] = Default::default(); }
fn acc(i: usize, v: u64) { ACC.with(|a| a[i].set(a[i].get() + v)); }
fn acc_take(i: usize) -> u64 { ACC.with(|a| a[i].take()) }
const A_MASKS: usize = 0; const A_LOOKUP: usize = 1; const A_CB: usize = 2; const A_PHRASE: usize = 3;
const A_RELEASE: usize = 4; const A_CSR: usize = 5; const A_NTOK: usize = 6; const A_NANCH: usize = 7;
const A_LIST: usize = 8; const A_BM: usize = 9; const A_NONE: usize = 10; const A_OTHER: usize = 11;
const A_LONG: usize = 12; const A_TOTAL: usize = 13;
// answer: 14 df sum, 15 tl build, 16 total bool, 17 probe path, 18 bitmap count/emit
static QK: [AtomicU64; 12] = [const { AtomicU64::new(0) }; 12];
static QA: [AtomicU64; 8] = [const { AtomicU64::new(0) }; 8];""")
# for_each_doc timers
rep("""    while i < hi {
        i += data[i..].iter().position(|&b| b == b'\\t').unwrap() + 1;""", """    while i < hi {
        let c0 = tsc();
        i += data[i..].iter().position(|&b| b == b'\\t').unwrap() + 1;""")
rep("""        let none = plan.role.len() as u32 - 1;
        let long =""", """        let c1 = tsc();
        let none = plan.role.len() as u32 - 1;
        let long =""")
rep("""        f(&tokens);
        tokens.clear();""", """        let c2 = tsc();
        f(&tokens);
        let c3 = tsc();
        // token classes not counted (see experiments/b-linux-profile/scan-report.json)
        acc(A_NTOK, tokens.len() as u64);
        let c4 = tsc();
        tokens.clear();""")
rep("""            release(&data[done..i]);
            done = i;
        }
    }""", """            release(&data[done..i]);
            done = i;
        }
        acc(A_MASKS, c1 - c0); acc(A_LOOKUP, c2 - c1); acc(A_CB, c3 - c2); acc(A_RELEASE, tsc() - c4);
    }""")
rep("""fn scan_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan, rows: &[AtomicU64]) -> Chunk {
""", """fn scan_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan, rows: &[AtomicU64]) -> Chunk {
    let ct = tsc();
""")
rep("""        let (anch, term) = (&anch[..m],""", """        let d0 = tsc();
        let (anch, term) = (&anch[..m],""")
rep("""        doc += 1;
    });""", """        acc(A_PHRASE, tsc() - d0);
        doc += 1;
    });""")
rep("""    // Counting sort of the stream""", """    let cf = tsc();
    // Counting sort of the stream""")
rep("""    offs[nl] = w as u32;
    Chunk { first, offs, docs, hits }""", """    offs[nl] = w as u32;
    acc(A_CSR, tsc() - cf);
    acc(A_TOTAL, tsc() - ct);
    let g: Vec<u64> = (0..14).map(acc_take).collect();
    writeln!(LOG.lock().unwrap(), "SCAN {:?} {lo} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {}", thread::current().id(),
        g[A_MASKS], g[A_LOOKUP], g[A_CB] - g[A_PHRASE], g[A_PHRASE], g[A_RELEASE], g[A_CSR], g[A_NTOK], g[A_NANCH], hits.len(),
        doc - first, g[A_LIST], g[A_BM], g[A_NONE], g[A_OTHER], g[A_LONG], g[A_TOTAL]).unwrap();
    Chunk { first, offs, docs, hits }""")
# boolean
rep("""    let (chunks, rows) = (&plan.chunks, &plan.rows);
    let words = s.bm.len();""", """    let q0 = tsc();
    let (mut used_bm, has_row) = (false, q.iter().any(|&(_, t)| plan.role[t as usize] & BITMAP != 0));
    let (chunks, rows) = (&plan.chunks, &plan.rows);
    let words = s.bm.len();""")
rep("""        let df: usize = chunks.iter().map(|c| c.post(t).len()).sum();""", """        let d0 = tsc();
        let df: usize = chunks.iter().map(|c| c.post(t).len()).sum();
        QA[0].fetch_add(tsc() - d0, Relaxed);""")
rep("""            r.retain(|&d| has(d) == and);
            continue;""", """            let p0 = tsc();
            r.retain(|&d| has(d) == and);
            QA[2].fetch_add(tsc() - p0, Relaxed);
            continue;""")
rep("""        tl.clear();
        for c in chunks {
            tl.extend(c.post(t).iter().map(|&d| c.first + d as u32));
        }""", """        let b0 = tsc();
        tl.clear();
        for c in chunks {
            tl.extend(c.post(t).iter().map(|&d| c.first + d as u32));
        }
        QA[1].fetch_add(tsc() - b0, Relaxed);
        QA[4].fetch_add(tl.len() as u64, Relaxed);""")
rep("""        match (is_bm, op) {
            (true, b'A') => {
                r.extend""", """        used_bm |= is_bm;
        match (is_bm, op) {
            (true, b'A') => {
                r.extend""")
rep("""    if !is_bm {
        return sorted_line(out, r.iter().copied());
    }""", """    used_bm |= is_bm;
    let kind = has_row as usize * 2 + used_bm as usize;
    if !is_bm {
        sorted_line(out, r.iter().copied());
        let d = tsc() - q0;
        QK[kind * 3].fetch_add(1, Relaxed); QK[kind * 3 + 1].fetch_add(d, Relaxed); QK[kind * 3 + 2].fetch_add(q.len() as u64, Relaxed);
        return;
    }
    let e0 = tsc();""")
rep("""    line(out, n, sum, ids);
    bm.fill(0);
}""", """    line(out, n, sum, ids);
    bm.fill(0);
    QA[3].fetch_add(tsc() - e0, Relaxed);
    let d = tsc() - q0;
    QK[kind * 3].fetch_add(1, Relaxed); QK[kind * 3 + 1].fetch_add(d, Relaxed); QK[kind * 3 + 2].fetch_add(q.len() as u64, Relaxed);
}""")
# main phases
rep("""fn main() {
""", """fn main() {
    T0.set(std::time::Instant::now()).unwrap();
    let tsc0 = tsc();
""")
rep("""    let mut plan = Plan::default();""", """    phase("read_queries");
    let mut plan = Plan::default();""")
rep("""    let data = map_file(&format!("{data_dir}/docs.txt"));""", """    phase("parse_intern");
    let data = map_file(&format!("{data_dir}/docs.txt"));
    phase("mmap");""")
rep("""    // A BOOL term in more than 1 of 32""", """    phase("sample_scan");
    // A BOOL term in more than 1 of 32""")
rep("""    // Equal byte ranges, each moved""", """    phase("plan_build");
    // Equal byte ranges, each moved""")
rep("""    let nchunks = nthreads *""", """    phase("rows_alloc");
    let nchunks = nthreads *""")
rep("""    chunks.sort_unstable_by_key(|c| c.0);""", """    phase("index");
    chunks.sort_unstable_by_key(|c| c.0);""")
rep("""    // Phrase matches as sorted""", """    phase("chunk_sort");
    // Phrase matches as sorted""")
rep("""    // Answer blocks of queries, claimed""", """    phase("hits_collect");
    // Answer blocks of queries, claimed""")
rep("""    outs.sort_unstable_by_key(|o| o.0);""", """    phase("answer");
    outs.sort_unstable_by_key(|o| o.0);""")
rep("""    fs::create_dir_all(&out_dir).ok();""", """    phase("outs_sort_concat");
    fs::create_dir_all(&out_dir).ok();""")
rep("""    std::process::exit(0); // the OS""", """    phase("write");
    let (c, t) = (tsc() - tsc0, ns());
    let mut log = LOG.lock().unwrap();
    writeln!(log, "TSC {:.6} {c} {t}", c as f64 / t as f64).unwrap();
    for (k, name) in ["bool_list", "bool_list_bm", "bool_row_list", "bool_row_bm"].iter().enumerate() {
        let g = |i: usize| QK[k * 3 + i].load(Relaxed);
        writeln!(log, "QKIND {name} {} {} 0 {}", g(0), (g(1) as f64 / (c as f64 / t as f64)) as u64, g(2)).unwrap();
    }
    for (k, name) in ["df_sum_cyc", "tl_build_cyc", "probe_cyc", "bm_emit_cyc", "tl_entries"].iter().enumerate() {
        writeln!(log, "INFO {name} {}", QA[k].load(Relaxed)).unwrap();
    }
    eprint!("{log}");
    std::process::exit(0); // the OS""")
sys.stdout.write(src)

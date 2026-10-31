static TEST_ACTIVE: AtomicUsize = AtomicUsize::new(0);
static TEST_FAST: AtomicUsize = AtomicUsize::new(0);
static TEST_FALLBACK: AtomicUsize = AtomicUsize::new(0);
static TEST_LEDGER: AtomicUsize = AtomicUsize::new(0);
static TEST_FAST_PUSH: AtomicUsize = AtomicUsize::new(0);
static TEST_EXACT_PUSH: AtomicUsize = AtomicUsize::new(0);
static TEST_CANCELLED: AtomicUsize = AtomicUsize::new(0);
static TEST_BUDGETFAIL: AtomicUsize = AtomicUsize::new(0);
static TEST_CAPFAIL: AtomicUsize = AtomicUsize::new(0);

struct TestWorker;
impl TestWorker {
    fn begin() -> Self { TEST_ACTIVE.fetch_add(1, Relaxed); Self }
}
impl Drop for TestWorker {
    fn drop(&mut self) { TEST_ACTIVE.fetch_sub(1, Relaxed); }
}

#[cfg(test)]
mod guarded_loader_review {
    use super::*;

    fn snapshot(graph: &Csr) -> Vec<(u32, u32, u64)> {
        let mut found = Vec::new();
        for u in 0..graph.first.len() - 1 {
            assert!(graph.first[u] <= graph.first[u + 1]);
            for (v, w) in graph.edges(u as u32) { found.push((u as u32, v, w)); }
        }
        found.sort_unstable();
        found
    }

    #[test]
    fn exact_multisets_worker_join_ledger_and_no_growth() {
        let variant = std::env::var("SD_TEST_VARIANT").unwrap();
        let path = std::env::temp_dir().join(format!("sd-guarded-loader-review-{}", std::process::id()));
        let mut state = 0x48b2_5c93_a91d_e1f1u64;
        let (mut cases, mut fast_cases, mut fallback_cases, mut cancellations) = (0,0,0,0);
        for &n in &[1usize, 2, 3, 7, 31, 64] {
            for &m in &[0usize, 1, 2, 7, 17, 64, 257, 1001] {
                for mode in 0..2 {
                    let mut input = format!("{n} {m}\n");
                    let mut forward = Vec::new();
                    for j in 0..m {
                        state ^= state << 13; state ^= state >> 7; state ^= state << 17;
                        let u = if mode == 0 { 0 } else { state as usize % n };
                        state ^= state << 13; state ^= state >> 7; state ^= state << 17;
                        let v = if mode == 0 { n - 1 } else { state as usize % n };
                        let w = [0u32, 1, 2046, 2047, u32::MAX, (state >> 32) as u32][j % 6];
                        input.push_str(&format!("{u} {v} {w}\n"));
                        forward.push((u as u32, v as u32, w as u64));
                    }
                    std::fs::write(&path, input.as_bytes()).unwrap();
                    forward.sort_unstable();
                    let mut backward: Vec<_> = forward.iter().map(|&(u, v, w)| (v, u, w)).collect();
                    backward.sort_unstable();
                    for threads in [1, 2, 3, 7, 12] {
                        for x in [&TEST_ACTIVE, &TEST_FAST, &TEST_FALLBACK, &TEST_LEDGER,
                                  &TEST_FAST_PUSH, &TEST_EXACT_PUSH, &TEST_CANCELLED,
                                  &TEST_BUDGETFAIL, &TEST_CAPFAIL] { x.store(0, Relaxed); }
                        let [f, b] = load_graph(path.to_str().unwrap(), threads);
                        let fast = TEST_FAST.load(Relaxed);
                        let fallback = TEST_FALLBACK.load(Relaxed);
                        assert_eq!(fast + fallback, 1, "{variant} n={n} m={m} t={threads}");
                        assert_eq!(TEST_ACTIVE.load(Relaxed), 0);
                        assert!(TEST_LEDGER.load(Relaxed) <= LOADER_BUDGET_BYTES);
                        if variant == "budget0" || variant == "budget1" || (variant == "cap0" && m > 0) {
                            assert_eq!(fallback, 1, "expected retry for {variant} n={n} m={m} t={threads}");
                        }
                        if variant == "budget0" || variant == "budget1" {
                            assert!(TEST_BUDGETFAIL.load(Relaxed) > 0, "missing budget rejection");
                        }
                        if variant == "cap0" && m > 0 {
                            assert!(TEST_CAPFAIL.load(Relaxed) > 0, "missing capacity rejection");
                        }
                        if fallback == 1 { assert_eq!(TEST_EXACT_PUSH.load(Relaxed), m); }
                        else { assert_eq!(TEST_FAST_PUSH.load(Relaxed), m); }
                        assert_eq!(f.first.len(), n + 1);
                        assert_eq!(b.first.len(), n + 1);
                        assert_eq!(f.first[n] as usize, m);
                        assert_eq!(b.first[n] as usize, m);
                        assert_eq!(snapshot(&f), forward, "{variant} n={n} m={m} mode={mode} t={threads}");
                        assert_eq!(snapshot(&b), backward, "{variant} n={n} m={m} mode={mode} t={threads}");
                        fast_cases += fast; fallback_cases += fallback;
                        cancellations += TEST_CANCELLED.load(Relaxed); cases += 1;
                    }
                }
            }
        }
        std::fs::remove_file(path).unwrap();
        assert!(fallback_cases > 0 || variant == "normal");
        if variant == "normal" { assert!(fast_cases > 0); }
        eprintln!("PASS {variant}: {cases} exact CSR cases, fast={fast_cases}, fallback={fallback_cases}, cancellations={cancellations}");
    }
}

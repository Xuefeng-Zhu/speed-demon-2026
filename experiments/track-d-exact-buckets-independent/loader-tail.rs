#[cfg(test)]
mod loader_review {
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
    fn chunk_boundaries_exact_capacity_and_both_directions() {
        let path = std::env::temp_dir().join(format!("sd-exact-loader-review-{}", std::process::id()));
        let mut state = 0x48b2_5c93_a91d_e1f1u64;
        let mut cases = 0;
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
                        let [f, b] = load_graph(path.to_str().unwrap(), threads);
                        assert_eq!(f.first.len(), n + 1);
                        assert_eq!(b.first.len(), n + 1);
                        assert_eq!(f.first[n] as usize, m);
                        assert_eq!(b.first[n] as usize, m);
                        assert_eq!(snapshot(&f), forward, "n={n} m={m} mode={mode} t={threads}");
                        assert_eq!(snapshot(&b), backward, "n={n} m={m} mode={mode} t={threads}");
                        cases += 1;
                    }
                }
            }
        }
        std::fs::remove_file(path).unwrap();
        eprintln!("PASS {cases} loader configurations including empty and skewed buckets");
    }
}

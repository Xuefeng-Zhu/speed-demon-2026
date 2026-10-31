#[cfg(test)]
mod hybrid_reuse_review {
    use super::*;

    fn graphs(n: usize, edges: &[(u32, u32, u32)]) -> [Csr; 2] {
        std::array::from_fn(|side| {
            let mut rows = vec![Vec::new(); n];
            for &(u, v, w) in edges {
                let (a, b) = if side == 0 { (u, v) } else { (v, u) };
                rows[a as usize].push((b, w));
            }
            let mut first = Vec::with_capacity(n + 1);
            let mut compact = Vec::new();
            let mut wide = Vec::new();
            first.push(0);
            for row in rows {
                for (v, w) in row {
                    compact.push((w.min(2047) << 21) | v);
                    wide.push(if w >= 2047 { w } else { 0 });
                }
                first.push(compact.len() as u32);
            }
            Csr { first, adj: Vec::new(), compact, wide }
        })
    }

    #[test]
    fn alternating_exhaustion_cutoff_zero_and_unreachable() {
        let mut edges = Vec::new();
        for v in 1..=10 { edges.push((0, v, v)); }
        edges.extend([
            (12, 13, u32::MAX), (13, 14, 7), (14, 15, 1), (15, 12, 0),
            (18, 19, 1), (19, 20, 2), (20, 21, 3), (21, 18, 1),
            (18, 20, 8), (20, 20, 0),
        ]);
        let [f, b] = graphs(24, &edges);
        let mut narrow = Search32::new(24);
        let mut wide = Search::new(24);
        let cases = [
            (0, 10, 10),
            (18, 21, 6),
            (12, 14, u32::MAX as u64 + 7),
            (18, 18, 0),
            (21, 19, 2),
            (0, 23, NONE),
            (13, 15, 8),
            (12, 13, u32::MAX as u64),
            (0, 1, 1),
            (15, 14, u32::MAX as u64 + 7),
        ];
        let mut reruns = 0;
        let mut narrow_answers = 0;
        let mut saw_forced_star = false;
        for _ in 0..250 {
            for &(s, t, expected) in &cases {
                let (n, dropped) = narrow.distance([&f, &b], s, t);
                if s == 0 && t == 10 && POOL_CAP <= 7 {
                    assert_eq!((n, dropped), (NONE, true));
                    saw_forced_star = true;
                }
                let got = if n < u32::MAX as u64 || !dropped {
                    narrow_answers += 1;
                    n
                } else {
                    reruns += 1;
                    wide.distance([&f, &b], s, t)
                };
                assert_eq!(got, expected, "cap={POOL_CAP}, {s}->{t}");
                assert!(narrow.touched.is_empty());
                assert!(narrow.dist.iter().all(|&d| d == [0, 0]));
                assert!(narrow.heaps.iter().all(|h| h.count == 0 && h.last == 0 && h.head.iter().all(|&v| v == END)));
                assert!(wide.touched.is_empty());
                assert!(wide.dist.iter().all(|&d| d == [0, 0]));
                assert!(wide.heaps.iter().all(|h| h.count == 0 && h.last == 0 && h.head.iter().all(|&v| v == END) && h.links.iter().all(|x| x[1] == UNLINKED)));
            }
        }
        assert!(reruns > 0);
        assert!(narrow_answers > 0);
        if POOL_CAP <= 7 { assert!(saw_forced_star); }
    }
}

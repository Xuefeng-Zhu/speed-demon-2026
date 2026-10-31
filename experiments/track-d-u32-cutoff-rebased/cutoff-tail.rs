#[cfg(test)]
mod cutoff_tests {
    use super::*;

    fn make_graph(n: usize, edges: &[(u32, u32, u32)]) -> [Csr; 2] {
        let mut graphs = Vec::new();
        for side in 0..2 {
            let mut rows: Vec<Vec<(u32, u32)>> = vec![Vec::new(); n];
            for &(u, v, w) in edges {
                let (a, b) = if side == 0 { (u, v) } else { (v, u) };
                rows[a as usize].push((b, w));
            }
            let mut first = vec![0];
            let mut compact = Vec::new();
            let mut wide = Vec::new();
            for row in rows {
                for (v, w) in row {
                    compact.push((w.min(2047) << 21) | v);
                    wide.push(if w >= 2047 { w } else { 0 });
                }
                first.push(compact.len() as u32);
            }
            graphs.push(Csr { first, adj: Vec::new(), compact, wide });
        }
        graphs.try_into().ok().unwrap()
    }

    #[test]
    fn cutoff_and_repeated_search_cleanup() {
        let cases = [
            (3, vec![], 0, 1, NONE, false),
            (3, vec![(0, 1, u32::MAX)], 0, 1, u32::MAX as u64, true),
            (3, vec![(0, 2, u32::MAX - 1), (2, 1, 1)], 0, 1, u32::MAX as u64, false),
            (3, vec![(0, 2, u32::MAX)], 0, 1, NONE, true),
            (3, vec![(0, 2, u32::MAX), (0, 1, 1)], 0, 1, 1, true),
            (3, vec![(0, 2, u32::MAX), (2, 1, 7)], 0, 1, u32::MAX as u64 + 7, true),
        ];
        for (n, edges, s, t, expected, expected_dropped) in cases {
            let graphs = make_graph(n, &edges);
            let mut narrow = Search32::new(n);
            let mut wide = Search::new(n);
            for _ in 0..128 {
                let (value, dropped) = narrow.distance([&graphs[0], &graphs[1]], s, t);
                assert_eq!(dropped, expected_dropped);
                let actual = if value < u32::MAX as u64 || !dropped { value } else {
                    wide.distance([&graphs[0], &graphs[1]], s, t)
                };
                assert_eq!(actual, expected);
                assert_eq!(narrow.distance([&graphs[0], &graphs[1]], s, s), (0, false));
            }
        }
    }
}

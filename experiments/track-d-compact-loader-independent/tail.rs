#[cfg(test)]
mod independent_bin_tests {
    use super::*;

    #[test]
    fn independent_mixed_and_boundary_bin_roundtrips() {
        let mut seed = 0x9e37_79b9_7f4a_7c15u64;
        let mut next = || { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; seed };
        let weights = [0u32, 1, 2045, 2046, 2047, 2048, 65535, 1 << 31, u32::MAX];
        let vertices = [0u32, 1, (1 << 20) - 1, 1 << 20, (1 << 21) - 2, (1 << 21) - 1];
        for pack in [false, true] {
            for capacity in [0usize, 1, 2, 17, 257] {
                let mut bins: Vec<_> = (0..7).map(|_| EdgeBin::new(capacity, pack)).collect();
                let mut expected = vec![Vec::<Edge>::new(); bins.len()];
                for i in 0..75_000usize {
                    let j = (next() as usize) % bins.len();
                    let (u, v) = if i % 3 == 0 {
                        (vertices[(i / 3) % vertices.len()], vertices[(i / 11) % vertices.len()])
                    } else {
                        ((next() as u32) & ((1 << 21) - 1), (next() as u32) & ((1 << 21) - 1))
                    };
                    let w = if i % 4 == 0 { next() as u32 } else { weights[i % weights.len()] };
                    bins[j].push(u, v, w); expected[j].push((u, v, w));
                }
                for (bin, reference) in bins.iter().zip(&expected) {
                    assert_eq!(bin.len(), reference.len());
                    let mut sources = Vec::new(); bin.sources(|u| sources.push(u));
                    assert!(sources.iter().copied().eq(reference.iter().map(|x| x.0)));
                    for _ in 0..3 {
                        let mut edges = Vec::new(); bin.edges(|u, v, w| edges.push((u,v,w)));
                        assert_eq!(&edges, reference);
                    }
                    if pack { assert_eq!(bin.overflow.len(), reference.iter().filter(|x| x.2 >= 2047).count()); }
                }
            }
        }
    }

    #[test]
    fn many_empty_bins_and_all_wide_weights() {
        let mut b = EdgeBin::new(0, true);
        let mut got = Vec::new(); b.edges(|u,v,w| got.push((u,v,w))); assert!(got.is_empty());
        for i in 0..200_000u32 { b.push(i, ((1 << 21) - 1) - i, u32::MAX - (i & 31)); }
        assert_eq!(b.overflow.len(), 200_000);
        let mut i = 0u32;
        b.edges(|u,v,w| { assert_eq!((u,v,w), (i, ((1 << 21)-1)-i, u32::MAX-(i&31))); i += 1; });
        assert_eq!(i, 200_000);
    }

    #[test]
    fn plain_mode_preserves_node_ids_above_packing_boundary() {
        let edges = [(1 << 21, (1 << 21) + 1, 2046),
                     ((1 << 21) + 1, 1 << 21, 2047),
                     (u32::MAX - 1, u32::MAX, u32::MAX)];
        let mut b = EdgeBin::new(0, false);
        for &(u,v,w) in &edges { b.push(u,v,w); }
        let mut decoded = Vec::new(); b.edges(|u,v,w| decoded.push((u,v,w)));
        assert_eq!(decoded.as_slice(), &edges);
        assert!(b.packed.is_empty() && b.overflow.is_empty());
    }
}

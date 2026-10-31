#[cfg(test)]
mod compact_loader_property {
    use super::*;

    fn step(s: &mut u64) -> u32 {
        *s ^= *s << 13; *s ^= *s >> 7; *s ^= *s << 17; *s as u32
    }

    #[test]
    fn exact_roundtrip_sources_and_overflow_order() {
        for &pack in &[true, false] {
            for &cap in &[0usize, 1, 7] {
                let mut bin = EdgeBin::new(cap, pack);
                let mut expected = Vec::new();
                let mut rng = 0x8c82_181f_e5a9_44d3;
                for i in 0..250_000u32 {
                    let mut u = step(&mut rng); let mut v = step(&mut rng);
                    if pack { u &= (1 << 21) - 1; v &= (1 << 21) - 1; }
                    let w = match i % 13 {
                        0 => 0, 1 => 2046, 2 => 2047, 3 => 2048,
                        4 => u32::MAX, 5 => 1, _ => step(&mut rng),
                    };
                    bin.push(u, v, w); expected.push((u, v, w));
                }
                assert_eq!(bin.len(), expected.len());
                let mut got = Vec::new(); bin.edges(|u, v, w| got.push((u, v, w)));
                assert_eq!(got, expected);
                let mut sources = Vec::new(); bin.sources(|u| sources.push(u));
                assert_eq!(sources, expected.iter().map(|e| e.0).collect::<Vec<_>>());
                if pack { assert_eq!(bin.overflow.len(), expected.iter().filter(|e| e.2 >= 2047).count()); }
                else { assert!(bin.packed.is_empty() && bin.overflow.is_empty()); }
            }
        }
        let mut packed = EdgeBin::new(0, true); let mut plain = EdgeBin::new(0, false);
        packed.edges(|_, _, _| panic!("unexpected")); plain.sources(|_| panic!("unexpected"));
        for (u,v,w) in [(0,0,0), ((1<<21)-1,(1<<21)-1,2046), (1,(1<<21)-1,2047),
                          (0,1,u32::MAX), ((1<<21)-1,1,2047)] {
            packed.push(u,v,w); plain.push(u,v,w);
        }
        let mut a=Vec::new();let mut b=Vec::new();
        packed.edges(|u,v,w| a.push((u,v,w)));plain.edges(|u,v,w| b.push((u,v,w)));
        assert_eq!(a,b);
    }

    #[test]
    fn loader_directed_edge_multisets_across_threads() {
        use std::io::Write;
        let dir = std::env::temp_dir().join(format!("sd-d-compact-loader-property-{}", std::process::id()));
        std::fs::create_dir(&dir).expect("fresh property directory");
        let path = dir.join("graph.txt");
        let mut rng = 0x61e1_14f5_8bc0_ee4du64;
        for case in 0..24usize {
            let n = [1usize, 2, 3, 7, 31, 127, 1023][case % 7];
            let m = [0usize, 1, 2, 13, 71, 501, 4099, 12017][case % 8];
            let mut fwd = vec![Vec::<(u32,u64)>::new();n];
            let mut rev = fwd.clone();
            let mut text = format!("{n} {m}\n");
            for i in 0..m {
                let u = (step(&mut rng) as usize % n) as u32;
                let v = if case % 4 == 0 { 0 } else { (step(&mut rng) as usize % n) as u32 };
                let w = match i % 8 { 0=>0,1=>2046,2=>2047,3=>2048,4=>u32::MAX,_=>step(&mut rng) };
                text.push_str(&format!("{u} {v} {w}\n"));
                fwd[u as usize].push((v,w as u64)); rev[v as usize].push((u,w as u64));
            }
            let mut file = std::fs::OpenOptions::new().create_new(true).write(true).open(&path).unwrap();
            file.write_all(text.as_bytes()).unwrap(); drop(file);
            for &threads in &[1usize,2,3,7,12] {
                let [a,b] = load_graph(path.to_str().unwrap(),threads);
                for u in 0..n {
                    let mut actual_a = a.edges(u as u32).collect::<Vec<_>>();
                    let mut actual_b = b.edges(u as u32).collect::<Vec<_>>();
                    actual_a.sort_unstable(); actual_b.sort_unstable();
                    let mut want_a = fwd[u].clone(); let mut want_b = rev[u].clone();
                    want_a.sort_unstable(); want_b.sort_unstable();
                    assert_eq!(actual_a,want_a,"forward case={case} t={threads} u={u}");
                    assert_eq!(actual_b,want_b,"reverse case={case} t={threads} u={u}");
                }
            }
            std::fs::remove_file(&path).unwrap();
        }
        std::fs::remove_dir(dir).unwrap();
    }
}

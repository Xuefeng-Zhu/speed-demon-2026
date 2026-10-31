#[cfg(test)]
mod vectored_tests {
    use super::write_ready;
    use std::io::{self, ErrorKind, IoSlice, Write};

    struct Fake {
        output: Vec<u8>, limit: usize, calls: usize, interrupt_every: usize,
        zero_at: Option<usize>, fail_at: Option<usize>, batches: usize,
    }
    impl Fake {
        fn new(limit: usize, interrupt_every: usize) -> Self {
            Self { output: Vec::new(), limit, calls: 0, interrupt_every,
                zero_at: None, fail_at: None, batches: 0 }
        }
    }
    impl Write for Fake {
        fn write(&mut self, b: &[u8]) -> io::Result<usize> {
            self.write_vectored(&[IoSlice::new(b)])
        }
        fn write_vectored(&mut self, slices: &[IoSlice<'_>]) -> io::Result<usize> {
            self.calls += 1;
            if slices.len() > 1 { self.batches += 1; }
            if self.zero_at == Some(self.calls) { return Ok(0); }
            if self.fail_at == Some(self.calls) { return Err(io::Error::new(ErrorKind::BrokenPipe, "injected")); }
            if self.interrupt_every != 0 && self.calls % self.interrupt_every == 0 {
                return Err(io::Error::from(ErrorKind::Interrupted));
            }
            let available: usize = slices.iter().map(|s| s.len()).sum();
            let mut left = available.min(self.limit);
            let result = left;
            for s in slices {
                let n = left.min(s.len());
                self.output.extend_from_slice(&s[..n]);
                left -= n;
                if left == 0 { break; }
            }
            Ok(result)
        }
        fn flush(&mut self) -> io::Result<()> { Ok(()) }
    }
    fn next(seed: &mut u64) -> u64 {
        *seed ^= *seed << 13; *seed ^= *seed >> 7; *seed ^= *seed << 17; *seed
    }
    #[test]
    fn out_of_order_and_forced_short_writes_match_oracle() {
        let mut seed = 0x625e_4a67_aa31_8115;
        let mut seen_batches = 0;
        for round in 0..160 {
            let groups: Vec<Vec<u8>> = (0..72).map(|i| {
                let len = match (i + round) % 7 { 0 => 0, 1 => 1, 2 => 2, 3 => 17, 4 => 65, 5 => 128, _ => 5 };
                (0..len).map(|_| next(&mut seed) as u8).collect()
            }).collect();
            let mut order: Vec<_> = (0..72).collect();
            for i in (1..72).rev() { let j = next(&mut seed) as usize % (i + 1); order.swap(i, j); }
            let mut p = vec![None; 72];
            let mut w = Fake::new([1, 3, 7, 128, usize::MAX][round % 5], [0, 3, 7, 11][round % 4]);
            let mut position = 0;
            for i in order {
                p[i] = Some(groups[i].clone());
                write_ready(&mut w, &mut p, &mut position).unwrap();
                let expected: Vec<u8> = groups[..position].iter().flatten().copied().collect();
                assert_eq!(w.output, expected);
            }
            assert_eq!(position, 72);
            assert!(p.iter().all(Option::is_none));
            seen_batches += w.batches;
        }
        assert!(seen_batches > 0, "must exercise multi-buffer writev");
    }
    #[test]
    fn empty_pending_and_empty_buffers() {
        let mut w = Fake::new(8, 0);
        let mut p = vec![None, Some(vec![])]; let mut pos = 0;
        write_ready(&mut w, &mut p, &mut pos).unwrap();
        assert_eq!(pos, 0); assert_eq!(w.calls, 0);
        p[0] = Some(vec![]);
        write_ready(&mut w, &mut p, &mut pos).unwrap();
        assert_eq!(pos, 2); assert_eq!(w.calls, 0);
    }
    #[test]
    fn failures_do_not_mark_batched_prefix_complete() {
        for zero in [false, true] {
            let mut w = Fake::new(1, 0);
            if zero { w.zero_at = Some(2); } else { w.fail_at = Some(2); }
            let mut p = vec![Some(b"ab".to_vec()), Some(b"cd".to_vec())];
            let mut pos = 0;
            let err = write_ready(&mut w, &mut p, &mut pos).unwrap_err();
            assert_eq!(err.kind(), if zero { ErrorKind::WriteZero } else { ErrorKind::BrokenPipe });
            assert_eq!(w.output, b"a"); assert_eq!(pos, 0);
            assert!(p.iter().all(Option::is_some));
        }
    }
}

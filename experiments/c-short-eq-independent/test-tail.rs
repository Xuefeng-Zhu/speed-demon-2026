#[cfg(test)]
mod independent_row_eq {
    use super::*;

    #[test]
    fn different_alignments_all_single_byte_values() {
        let mut left = [0u8; 160];
        let mut right = [0u8; 160];
        for n in 0..=32usize {
            for offset in 0..64usize {
                let other = (offset * 29 + 7) % 64;
                for i in 0..n { left[offset + i] = (i as u8).wrapping_mul(59).wrapping_add(offset as u8); }
                right[other..other+n].copy_from_slice(&left[offset..offset+n]);
                assert!(row_name_equal(&left[offset..offset+n], &right[other..other+n]));
                for at in 0..n {
                    let original = right[other + at];
                    for replacement in 0..=u8::MAX {
                        right[other + at] = replacement;
                        assert_eq!(row_name_equal(&left[offset..offset+n], &right[other..other+n]), replacement == original, "n={n} offset={offset} at={at} replacement={replacement}");
                    }
                    right[other + at] = original;
                }
                if n < 32 {
                    assert!(!row_name_equal(&left[offset..offset+n], &right[other..other+n+1]));
                }
            }
        }
    }

    #[test]
    fn randomized_bytes_overlap_and_identical_slices() {
        let mut state = 0x1234_5678_9abc_def0u64;
        let mut buf = [0u8; 512];
        for _ in 0..500_000 {
            state ^= state << 13; state ^= state >> 7; state ^= state << 17;
            let a = (state as usize) % 256;
            let b = ((state >> 9) as usize) % 256;
            let na = ((state >> 18) as usize) % 65;
            let nb = ((state >> 26) as usize) % 65;
            buf[(state as usize >> 32) % 512] ^= (state >> 48) as u8;
            let x = &buf[a..a+na];
            let y = &buf[b..b+nb];
            assert_eq!(row_name_equal(x,y), x == y);
            assert!(row_name_equal(x,x));
        }
    }
}

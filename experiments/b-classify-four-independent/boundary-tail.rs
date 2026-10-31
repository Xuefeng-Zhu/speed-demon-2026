#[cfg(test)]
mod independent_four_boundaries {
    use super::*;

    fn expected(body: &[u8], plan: &Plan<'_>) -> Vec<u32> {
        let mut tokens = Vec::new();
        let mut start = None;
        for i in 0..=body.len() {
            if i < body.len() && body[i].is_ascii_alphanumeric() {
                if start.is_none() { start = Some(i); }
            } else if let Some(s) = start.take() {
                let n = i - s;
                tokens.push(if n <= 32 { plan.lookup_token(body, s, n) } else { MISS });
            }
        }
        tokens
    }

    #[test]
    fn four_block_transitions_and_phrase_order() {
        let mut plan = Plan { slots: vec![MISS; 512], ..Default::default() };
        for n in 1..=32 { plan.intern(&vec![b'a'; n], IN_BOOL); }
        let phrase: Vec<_> = [b"x".as_slice(), b"alpha", b"9z"].iter()
            .map(|s| plan.intern(s, IN_BOOL)).collect();
        plan.build_short();
        let mut bytes = Vec::new();
        let mut ranges = Vec::new();
        for size in [127usize, 128, 129, 255, 256, 257] {
            for boundary in [32usize, 64, 96, 128, 160, 192, 224, 256] {
                if boundary >= size { continue; }
                for left in [1usize, 2, 15, 16, 31, 32, 33] {
                    for right in [1usize, 2, 15, 16, 31, 32, 33] {
                        if boundary < left || boundary + right > size { continue; }
                        let mut body = vec![b'-'; size];
                        for b in &mut body[boundary-left..boundary+right] { *b = b'A'; }
                        // UTF-8 high bytes are separators; placement avoids the token.
                        if boundary > left + 3 { body[0..3].copy_from_slice(&[0xe2, 0x82, 0xac]); }
                        bytes.extend_from_slice(b"0\t");
                        let start = bytes.len(); bytes.extend_from_slice(&body);
                        ranges.push((start, bytes.len(), false)); bytes.push(b'\n');
                    }
                }
                let literal = b"x-alpha-9z";
                for left in [1usize, 2, 5, 7] {
                    if boundary < left || boundary-left + literal.len() > size { continue; }
                    let mut body = vec![b'-'; size];
                    body[boundary-left..boundary-left+literal.len()].copy_from_slice(literal);
                    bytes.extend_from_slice(b"0\t");
                    let start = bytes.len(); bytes.extend_from_slice(&body);
                    ranges.push((start, bytes.len(), true)); bytes.push(b'\n');
                }
            }
        }
        let mut doc = 0;
        for_each_doc(&bytes, 0, bytes.len(), &plan, |tokens| {
            let (lo, hi, has_phrase) = ranges[doc];
            let expected_tokens = expected(&bytes[lo..hi], &plan);
            assert_eq!(tokens, expected_tokens, "document {doc} body length {}", hi-lo);
            let hits = tokens.windows(phrase.len()).filter(|w| *w == phrase.as_slice()).count();
            assert_eq!(hits, usize::from(has_phrase), "phrase order in document {doc}");
            doc += 1;
        });
        assert_eq!(doc, ranges.len());
        assert!(doc > 1_000);
        println!("PASS {doc} 127/128/129/255/256/257-byte four-block boundary documents");
    }

    #[cfg(any(target_os = "linux", target_os = "macos"))]
    #[test]
    fn guarded_document_scans_at_both_page_ends() {
        unsafe extern "C" {
            fn getpagesize() -> i32;
            fn mprotect(addr: *mut u8, len: usize, prot: i32) -> i32;
            fn munmap(addr: *mut u8, len: usize) -> i32;
        }
        #[cfg(target_os = "macos")]
        const MAP_ANON: i32 = 0x1000;
        #[cfg(target_os = "linux")]
        const MAP_ANON: i32 = 0x20;

        let mut plan = Plan { slots: vec![MISS; 512], ..Default::default() };
        for n in 1..=32 { plan.intern(&vec![b'a'; n], IN_BOOL); }
        for word in [b"x".as_slice(), b"alpha", b"9z"] { plan.intern(word, IN_BOOL); }
        plan.build_short();
        let mut cases = 0;
        unsafe {
            let page = getpagesize() as usize;
            let base = mmap(std::ptr::null_mut(), page * 3, 3, 2 | MAP_ANON, -1, 0);
            assert_ne!(base as isize, -1);
            assert!(!base.is_null());
            assert_eq!(mprotect(base, page, 0), 0);
            assert_eq!(mprotect(base.add(2 * page), page, 0), 0);

            for size in [127usize, 128, 129, 255, 256, 257] {
                for pattern in 0..4 {
                    let mut body = vec![b'-'; size];
                    match pattern {
                        0 => body.fill(b'A'), // one token longer than 32, crossing all boundaries
                        1 => for (i, b) in body.iter_mut().enumerate() {
                            *b = if i % 64 < 49 { b'a' } else if i % 3 == 0 { 0xe2 } else { b'-' };
                        },
                        2 => for (i, b) in body.iter_mut().enumerate() {
                            *b = if i % 32 < 17 { b'A' } else if i % 32 < 25 { b'7' } else { b'-' };
                        },
                        _ => {
                            let phrase = b"x-alpha-9z";
                            for start in [28usize, 60, 92] {
                                if start + phrase.len() <= size { body[start..start+phrase.len()].copy_from_slice(phrase); }
                            }
                            if size > 132 { body[123..132].fill(b'A'); }
                        },
                    }
                    let want = expected(&body, &plan);
                    let mut doc = b"0\t".to_vec();
                    doc.extend_from_slice(&body); doc.push(b'\n');
                    assert!(doc.len() < page);
                    for at in [base.add(page), base.add(2 * page - doc.len())] {
                        std::ptr::copy_nonoverlapping(doc.as_ptr(), at, doc.len());
                        let data = std::slice::from_raw_parts(at, doc.len());
                        let mut calls = 0;
                        for_each_doc(data, 0, data.len(), &plan, |tokens| {
                            assert_eq!(tokens, want, "size {size}, pattern {pattern}");
                            calls += 1;
                        });
                        assert_eq!(calls, 1);
                        cases += 1;
                    }
                }
            }
            assert_eq!(munmap(base, page * 3), 0);
        }
        assert_eq!(cases, 48);
        println!("PASS {cases} guarded whole-document scans at both page ends");
    }
}

#[cfg(test)]
mod independent_two_lane {
    use super::*;

    #[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
    struct Record { hour: usize, endpoint: Vec<u8>, latency: u32, error: u32 }

    fn corpus(n: usize) -> (Vec<u8>, Vec<usize>, Vec<Record>) {
        let mut data = Vec::new();
        let mut starts = vec![0];
        let mut expected = Vec::new();
        let methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];
        let latencies = [0u32, 1, 1_048_574, 1_048_575, 1_048_576, u32::MAX, 51];
        for i in 0..n {
            let hour = (i * 37 + 11) % 72;
            let absolute = hour + 18;
            let day = absolute / 24;
            let (month, date) = [(10, 30), (10, 31), (11, 1), (11, 2)][day];
            let name = if i % 31 == 0 { "/".to_string() }
                else if i % 37 == 0 { format!("/{}", "a".repeat(124)) }
                else if i % 11 == 0 { format!("/duplicate/{}", i % 13) }
                else { format!("/p/{i:05}") };
            let latency = latencies[i % latencies.len()];
            let status = [100, 499, 500, 599][i % 4];
            let line = format!("2026-{month:02}-{date:02}T{:02}:{:02}:{:02}.{:06}Z {} {name} {status} {latency}\n",
                absolute % 24, (i * 19) % 60, (i * 29) % 60, i % 1_000_000, methods[i % methods.len()]);
            data.extend_from_slice(line.as_bytes());
            starts.push(data.len());
            expected.push(Record { hour, endpoint: name.into_bytes(), latency, error: u32::from(status >= 500) });
        }
        data.resize(data.len() + 4096, 0);
        (data, starts, expected)
    }

    fn decode(data: &[u8], chunk: &Chunk) -> Vec<Record> {
        let mut records = Vec::new();
        for (hour, entries) in chunk.hours.iter().enumerate() {
            let mut escapes = chunk.escapes[hour].iter();
            for &entry in entries {
                let (id, error, latency) = if entry == u32::MAX {
                    let x = *escapes.next().expect("missing escape");
                    ((x >> 33) as usize, ((x >> 32) & 1) as u32, x as u32)
                } else {
                    ((entry >> 21) as usize, (entry >> 20) & 1, entry & 0x000f_ffff)
                };
                let (_, start, end) = chunk.table.names[id];
                records.push(Record { hour, endpoint: data[start..end].to_vec(), latency, error });
            }
            assert!(escapes.next().is_none(), "unconsumed escape at hour {hour}");
        }
        records.sort();
        records
    }

    fn compare(data: &[u8], starts: &[usize], expected: &[Record], a: usize, b: usize) {
        let got = decode(data, &parse(data, starts[a], starts[b]));
        let mut want = expected[a..b].to_vec();
        want.sort();
        assert_eq!(got, want, "interval [{a}, {b})");
    }

    #[test]
    fn all_line_aligned_subranges_and_many_ids() {
        let (data, starts, expected) = corpus(64);
        for a in 0..=64 { for b in a..=64 { compare(&data, &starts, &expected, a, b); } }
        let (data, starts, expected) = corpus(2500);
        compare(&data, &starts, &expected, 0, 2500);
        for a in (0..2500).step_by(97) {
            for length in [0, 1, 2, 3, 17, 127, 1023, 2499] {
                compare(&data, &starts, &expected, a, (a + length).min(2500));
            }
        }
    }
}

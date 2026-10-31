from pathlib import Path
import hashlib

root = Path(__file__).resolve().parents[2]
source = (root / 'track-a/src/main.rs').read_text()
assert hashlib.sha256(source.encode()).hexdigest() == '4af40353f517f566217b0f882ec25d8002f61d211dcc479c53f8a1dd5de7ed88'
out = Path(__file__).resolve().parent
(out / 'baseline.rs').write_text(source)
start = source.index('fn parse(d: &[u8], mut i: usize, end: usize) -> Chunk {')
end = source.index('\nfn push_num(', start)
replacement = r'''#[inline(always)]
fn record_hour(d: &[u8], i: usize) -> usize {
    let digit = |k: usize| (d[i + k] - b'0') as usize;
    let day = digit(8) * 10 + digit(9) + 31 * digit(6) - 30;
    day * 24 + digit(11) * 10 + digit(12) - 18
}

#[inline(always)]
fn append_record(c: &mut Chunk, hour: usize, id: u64, latency: u64, is_5xx: u64) {
    if id < 2048 && latency < 0x000f_ffff {
        c.hours[hour].push(((id as u32) << 21) | ((is_5xx as u32) << 20) | latency as u32);
    } else {
        c.hours[hour].push(u32::MAX);
        c.escapes[hour].push(id << 33 | is_5xx << 32 | latency);
    }
}

#[inline(always)]
fn endpoint(d: &[u8], s: usize) -> (usize, u64) {
    let (mut e, mut h) = (s, 0u64);
    loop {
        let w = load(d, e);
        let k = find_byte(w, b' ');
        if k < 8 {
            return (e + k, (h ^ (w & ((1 << (8 * k)) - 1)) ^ k as u64).wrapping_mul(MIX));
        }
        h = (h ^ w).wrapping_mul(MIX);
        e += 8;
    }
}

#[inline(always)]
fn one(d: &[u8], i: usize, c: &mut Chunk) -> usize {
    let hour = record_hour(d, i);
    let s = i + 29 + find_byte(load(d, i + 28), b' ');
    let (e, h) = endpoint(d, s);
    let id = c.table.find(d, h, s, e) as u64;
    let (latency, next) = parse_latency(d, e + 5);
    append_record(c, hour, id, latency, (d[e + 1] == b'5') as u64);
    next
}

fn parse(d: &[u8], i: usize, end: usize) -> Chunk {
    let (table, hours, escapes) = (Table::default(), vec![Vec::new(); HOURS], vec![Vec::new(); HOURS]);
    let mut c = Chunk { table, hours, escapes };
    // Align the interior split to a whole line; collapsed halves are valid.
    let mut mid = i + (end - i) / 2;
    while mid > i && mid < end && d[mid - 1] != b'\n' { mid += 1; }
    let (mut a, mut b) = (i, mid);
    while a < mid && b < end {
        let (hour_a, hour_b) = (record_hour(d, a), record_hour(d, b));
        let (sa, sb) = (a + 29 + find_byte(load(d, a + 28), b' '), b + 29 + find_byte(load(d, b + 28), b' '));
        let (mut ea, mut eb, mut ha, mut hb, mut live_a, mut live_b) = (sa, sb, 0u64, 0u64, true, true);
        while live_a || live_b {
            if live_a {
                let w = load(d, ea); let k = find_byte(w, b' ');
                if k < 8 { ha = (ha ^ (w & ((1 << (8*k))-1)) ^ k as u64).wrapping_mul(MIX); ea += k; live_a = false; }
                else { ha = (ha ^ w).wrapping_mul(MIX); ea += 8; }
            }
            if live_b {
                let w = load(d, eb); let k = find_byte(w, b' ');
                if k < 8 { hb = (hb ^ (w & ((1 << (8*k))-1)) ^ k as u64).wrapping_mul(MIX); eb += k; live_b = false; }
                else { hb = (hb ^ w).wrapping_mul(MIX); eb += 8; }
            }
        }
        let id_a = c.table.find(d, ha, sa, ea) as u64;
        let id_b = c.table.find(d, hb, sb, eb) as u64;
        let (lat_a, next_a) = parse_latency(d, ea + 5);
        let (lat_b, next_b) = parse_latency(d, eb + 5);
        append_record(&mut c, hour_a, id_a, lat_a, (d[ea + 1] == b'5') as u64);
        append_record(&mut c, hour_b, id_b, lat_b, (d[eb + 1] == b'5') as u64);
        (a, b) = (next_a, next_b);
    }
    while a < mid { a = one(d, a, &mut c); }
    while b < end { b = one(d, b, &mut c); }
    c
}
'''
(out / 'candidate.rs').write_text(source[:start] + replacement + source[end:])

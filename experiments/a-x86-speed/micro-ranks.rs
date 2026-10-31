//! Single-thread microbenchmark of the small-group percentile paths (local diagnostic only).
//! Random groups of 1..=maxn values (uniform below 200,000), about 3 million values per size
//! class; mode 0 is the previous sort (n <= 16) or three select_nth_unstable calls, mode 1 the
//! AVX2 rank counting of `s1e-small-ranks.rs` for n <= 64 (else mode 0), mode 2 a trivial
//! read of three values (harness floor). Matching `acc` values mean identical answers.
//! Build: rustc --edition 2021 -C opt-level=3 -C target-cpu=x86-64-v3 micro-ranks.rs
/// Values of ranks `r` in `v` (n <= 8 * V values, read from `v.as_ptr()` up to 8 * V values ahead):
/// the value of rank r is the largest value with at most r values below it.
#[inline(always)]
fn small_ranks<const V: usize>(v: &[u32], r: [usize; 3]) -> [u32; 3] {
    use std::arch::x86_64::*;
    let n = v.len();
    unsafe {
        let bias = _mm256_set1_epi32(i32::MIN);
        let iota = _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7);
        let x: [__m256i; V] = std::array::from_fn(|k| {
            let live = _mm256_cmpgt_epi32(_mm256_set1_epi32(n as i32), _mm256_add_epi32(iota, _mm256_set1_epi32(8 * k as i32)));
            let w = _mm256_loadu_si256(v.as_ptr().add(8 * k).cast());
            _mm256_xor_si256(_mm256_blendv_epi8(_mm256_set1_epi32(-1), w, live), bias)
        });
        let mut below = [_mm256_setzero_si256(); V];
        for &y in v {
            let y = _mm256_set1_epi32((y ^ 0x8000_0000) as i32);
            for k in 0..V {
                below[k] = _mm256_sub_epi32(below[k], _mm256_cmpgt_epi32(x[k], y));
            }
        }
        r.map(|r| {
            let r = _mm256_set1_epi32(r as i32);
            let mut m = _mm256_setzero_si256();
            for k in 0..V {
                let keep = _mm256_andnot_si256(_mm256_cmpgt_epi32(below[k], r), _mm256_xor_si256(x[k], bias));
                m = _mm256_max_epu32(m, keep);
            }
            let m = _mm256_max_epu32(m, _mm256_permute2x128_si256(m, m, 1));
            let m = _mm256_max_epu32(m, _mm256_shuffle_epi32(m, 0b01_00_11_10));
            let m = _mm256_max_epu32(m, _mm256_shuffle_epi32(m, 0b10_11_00_01));
            _mm256_cvtsi256_si32(m) as u32
        })
    }
}
fn old(v: &mut [u32], r50: usize, r95: usize, r99: usize) -> [u32;3] {
    let n = v.len();
    if n <= 16 { v.sort_unstable(); } else {
        v.select_nth_unstable(r50);
        if r95 > r50 { v[r50 + 1..].select_nth_unstable(r95 - r50 - 1); }
        if r99 > r95 { v[r95 + 1..].select_nth_unstable(r99 - r95 - 1); }
    }
    [v[r50], v[r95], v[r99]]
}
fn main() {
    let mut x: u64 = 88172645463325252;
    let mut rnd = || { x ^= x << 13; x ^= x >> 7; x ^= x << 17; x };
    for &maxn in &[8usize, 16, 32, 64, 128, 4096] {
        let mut sizes = vec![]; let mut data = vec![];
        let mut tot = 0;
        while tot < 3_000_000 { let n = 1 + (rnd() as usize % maxn); sizes.push(n); tot += n; }
        for _ in 0..tot+64 { data.push((rnd() % 200000) as u32); }
        for mode in 0..3 {
            let mut d = data.clone();
            let t = std::time::Instant::now();
            let mut acc = 0u64; let mut at = 0;
            for &n in &sizes {
                let v = &mut d[at..at+n]; at += n;
                let f = |p: usize| (p * n + 99) / 100 - 1;
                let (r50,r95,r99)=(f(50),f(95),f(99));
                let p = if mode==2 { [v[0],v[n/2],v[n-1]] } else if mode==0 { old(v,r50,r95,r99) } else if n<=8 { small_ranks::<1>(v,[r50,r95,r99]) } else if n<=16 { small_ranks::<2>(v,[r50,r95,r99]) } else if n<=32 { small_ranks::<4>(v,[r50,r95,r99]) } else if n<=64 { small_ranks::<8>(v,[r50,r95,r99]) } else { old(v,r50,r95,r99) };
                acc = acc.wrapping_mul(31).wrapping_add((p[0]^p[1]^p[2]) as u64);
            }
            let el = t.elapsed().as_secs_f64();
            println!("maxn {maxn} mode {mode} groups {} ns/group {:.1} ns/elem {:.2} acc {acc}", sizes.len(), el*1e9/sizes.len() as f64, el*1e9/tot as f64);
        }
    }
}

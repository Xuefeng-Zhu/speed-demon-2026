import sys
# mkcand.py SRC DST: the D build-phase candidate (parallel huge-page first touch, divide-free
# bucket index) with final comments.
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, a
    s = s.replace(a, b)
rep('''/// `len` zeros, on huge pages where the kernel allows: fewer page faults to
/// fill the array and fewer TLB misses to search it.
fn zeros(len: usize) -> Vec<u32> {
    let v = vec![0u32; len];
    let huge = |p: usize| (v.as_ptr() as usize + p) & !((1 << 21) - 1);
    let (a, b) = (huge((1 << 21) - 1), huge(len * 4));
    if a < b {
        unsafe { madvise(a as *mut u8, b - a, 14) }; // MADV_HUGEPAGE
                                                     // One first writer per huge page: racing faults each charge a 2 MiB page.
        (a..b)
            .step_by(1 << 21)
            .for_each(|p| unsafe { (p as *mut u8).write_volatile(0) });
    }
    v
}''', '''/// `len` zeros, on huge pages where the kernel allows: fewer page faults to
/// fill the array and fewer TLB misses to search it. Each huge page gets one
/// first writer (racing faults would each charge a 2 MiB page), and the
/// `threads` writers take every `threads`-th page, so the kernel zeroes the
/// pages in parallel.
fn zeros(len: usize, threads: usize) -> Vec<u32> {
    let v = vec![0u32; len];
    let huge = |p: usize| (v.as_ptr() as usize + p) & !((1 << 21) - 1);
    let (a, b) = (huge((1 << 21) - 1), huge(len * 4));
    if a < b {
        unsafe { madvise(a as *mut u8, b - a, 14) }; // MADV_HUGEPAGE
        parallel(threads, &|i| {
            let pages = (a + (i << 21)..b).step_by(threads << 21);
            pages.for_each(|p| unsafe { (p as *mut u8).write_volatile(0) })
        });
    }
    v
}''')
rep('''    let block_len = n.div_ceil(threads);
''', '''    let block_len = n.div_ceil(threads);
    let inv = (1u128 << 64) / block_len as u128 + 1; // u * inv >> 64 is u / block_len
''')
rep('''lists[u as usize / block_len]''', '''lists[(u as u128 * inv >> 64) as usize]''')
rep('(zeros(n + 1), zeros(m))', '(zeros(n + 1, threads), zeros(m, threads))')
rep('(vec![0; n], zeros(n + 1), zeros(m))', '(vec![0; n], zeros(n + 1, threads), zeros(m, threads))')
open(dst, 'w').write(s)
print('ok')

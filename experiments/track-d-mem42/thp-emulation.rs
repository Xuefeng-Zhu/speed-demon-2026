// Diagnostic only, pasted into a profile copy before `parallel`: emulates THP
// "always" for large heap blocks. Every block of 128 KiB or more (glibc mmaps
// those, given the fixed threshold) gets MADV_HUGEPAGE, so faults in 2 MiB
// aligned ranges of the block's mapping could be served with huge pages.
// Result on the baseline: no AnonHugePages after the parse (the bucket lists
// stay on 4 KiB pages, since glibc writes each block's header at once) and an
// unchanged peak, so this gives no support to THP as the reason the board's M
// is higher than the local peak. See README.md.
struct ThpAlloc;
unsafe impl std::alloc::GlobalAlloc for ThpAlloc {
    unsafe fn alloc(&self, l: std::alloc::Layout) -> *mut u8 {
        let p = std::alloc::System.alloc(l);
        hint(p, l.size());
        p
    }
    unsafe fn alloc_zeroed(&self, l: std::alloc::Layout) -> *mut u8 {
        let p = std::alloc::System.alloc_zeroed(l);
        hint(p, l.size());
        p
    }
    unsafe fn dealloc(&self, p: *mut u8, l: std::alloc::Layout) {
        std::alloc::System.dealloc(p, l)
    }
    unsafe fn realloc(&self, p: *mut u8, l: std::alloc::Layout, n: usize) -> *mut u8 {
        let q = std::alloc::System.realloc(p, l, n);
        hint(q, n);
        q
    }
}
unsafe fn hint(p: *mut u8, len: usize) {
    if len >= 1 << 17 && !p.is_null() {
        let a = (p as usize - 16) & !4095; // glibc's mmapped chunk header sits just before p
        madvise(a as *mut u8, (p as usize + len - a + 4095) & !4095, 14);
    }
}
#[global_allocator]
static A: ThpAlloc = ThpAlloc;

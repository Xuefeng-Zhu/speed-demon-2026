// Shows the kernel allocating, charging and discarding huge pages when several threads
// first-write the same empty 2 MiB-aligned range of a huge-page-eligible mapping at once.
//
//   rustc -O thp-race.rs && ./thp-race THREADS ADVICE     (ADVICE 14 = MADV_HUGEPAGE, 15 = MADV_NOHUGEPAGE)
//
// Prints system-wide /proc/vmstat deltas, so run it on an otherwise idle machine. A huge
// page is 512 pages: with 8 threads and advice 14 the sandbox showed about 4,200 pages
// allocated, 3,590 freed and one huge page installed, against 524 pages for one thread.
use std::{collections::HashMap, fs, sync::Barrier, thread};

extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn madvise(addr: *mut u8, len: usize, advice: i32) -> i32;
}

fn vmstat() -> HashMap<String, i64> {
    let text = fs::read_to_string("/proc/vmstat").unwrap();
    let pairs = text.lines().map(|l| {
        let mut f = l.split_whitespace();
        (f.next().unwrap().to_string(), f.next().unwrap().parse().unwrap())
    });
    pairs.collect()
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let (n, advice): (usize, i32) = (a[1].parse().unwrap(), a[2].parse().unwrap());
    let base = unsafe { mmap(0 as _, 8 << 20, 3, 0x22, -1, 0) } as usize;
    let aligned = (base + (2 << 20) - 1) & !((2 << 20) - 1);
    unsafe { madvise(base as _, 8 << 20, advice) };
    let barrier = Barrier::new(n);
    let v0 = vmstat();
    thread::scope(|s| {
        for t in 0..n {
            let b = &barrier;
            s.spawn(move || {
                b.wait();
                unsafe { *((aligned + t * 65536) as *mut u64) = 1 };
            });
        }
    });
    let v1 = vmstat();
    let d = |k: &str| v1.get(k).unwrap_or(&0) - v0.get(k).unwrap_or(&0);
    let alloc = ["pgalloc_dma", "pgalloc_dma32", "pgalloc_normal", "pgalloc_movable"];
    let alloc: i64 = alloc.iter().map(|k| d(k)).sum();
    println!(
        "threads {n} advice {advice}: pages allocated {alloc}, freed {}, huge pages installed {}",
        d("pgfree"),
        d("thp_fault_alloc")
    );
}

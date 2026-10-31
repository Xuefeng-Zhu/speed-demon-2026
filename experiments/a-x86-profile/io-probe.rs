//! I/O and page-fault floor probe for Track A, without any parsing.
//!
//! Usage: io-probe <file> <threads> <mode> [buf_kib]
//! Modes:
//!   mmap-touch / mmap-sum                     production-style map_file, read one u64 per 4 KiB
//!                                             page (touch) or sum every u64 (sum), then
//!                                             madvise(MADV_DONTNEED) the chunk
//!   mmap-nodontneed-touch / mmap-nodontneed-sum  same without madvise
//!   mmap-populate-sum                         MAP_POPULATE on the file mapping, sum, madvise
//!   pread                                     pread the chunk sequentially into one reused
//!                                             per-thread buffer of buf_kib KiB and sum every u64
//! The file is split into the same newline-aligned per-thread chunks as production. Output is
//! key value lines on stderr. Build: rustc -C opt-level=3 -C target-cpu=x86-64-v3 io-probe.rs
use std::os::unix::io::AsRawFd;
use std::time::Instant;
use std::{env, fs, thread};

extern "C" {
    fn mmap(addr: *mut u8, len: usize, prot: i32, flags: i32, fd: i32, off: i64) -> *mut u8;
    fn madvise(addr: *const u8, len: usize, advice: i32) -> i32;
    fn pread(fd: i32, buf: *mut u8, count: usize, off: i64) -> isize;
    fn getrusage(who: i32, usage: *mut RUsage) -> i32;
    fn clock_gettime(clock: i32, ts: *mut [i64; 2]) -> i32;
}

/// Exact CPU time in seconds (getrusage times are tick-sampled): 2 = process, 3 = this thread.
fn cpu(clock: i32) -> f64 {
    let mut ts = [0i64; 2];
    unsafe { clock_gettime(clock, &mut ts) };
    ts[0] as f64 + ts[1] as f64 * 1e-9
}

/// Linux x86_64 `struct rusage`: two timevals, then 14 longs.
#[repr(C)]
#[derive(Clone, Copy, Default)]
struct RUsage {
    utime_s: i64,
    utime_us: i64,
    stime_s: i64,
    stime_us: i64,
    maxrss: i64,
    ixrss: i64,
    idrss: i64,
    isrss: i64,
    minflt: i64,
    majflt: i64,
    nswap: i64,
    inblock: i64,
    oublock: i64,
    msgsnd: i64,
    msgrcv: i64,
    nsignals: i64,
    nvcsw: i64,
    nivcsw: i64,
}

impl RUsage {
    fn user(&self) -> f64 {
        self.utime_s as f64 + self.utime_us as f64 * 1e-6
    }
    fn sys(&self) -> f64 {
        self.stime_s as f64 + self.stime_us as f64 * 1e-6
    }
}

fn ru(who: i32) -> RUsage {
    let mut r = RUsage::default();
    unsafe { getrusage(who, &mut r) };
    r
}

fn status_kb(keys: &[&str]) -> Vec<u64> {
    let s = fs::read_to_string("/proc/self/status").unwrap_or_default();
    keys.iter()
        .map(|k| {
            s.lines()
                .find(|l| l.starts_with(k) && l[k.len()..].starts_with(':'))
                .and_then(|l| l[k.len() + 1..].trim().trim_end_matches("kB").trim().parse().ok())
                .unwrap_or(0)
        })
        .collect()
}

/// Same layout as production map_file: anonymous reserve of len + 4096, file mapped over it.
fn map_file(file: &fs::File, len: usize, extra_flags: i32) -> &'static [u8] {
    let (read, private, fixed, anon, null) = (1, 2, 0x10, 0x20, std::ptr::null_mut());
    unsafe {
        let base = mmap(null, len + 4096, read, private | anon, -1, 0);
        assert!(base as isize > 0, "mmap failed");
        let fd = file.as_raw_fd();
        assert!(len == 0 || mmap(base, len, read, private | fixed | extra_flags, fd, 0) == base);
        std::slice::from_raw_parts(base, len + 4096)
    }
}

/// Wrapping sum of the little-endian u64 words of `b`, the tail zero-padded.
fn sum_words(b: &[u8]) -> u64 {
    let mut it = b.chunks_exact(8);
    let mut s = 0u64;
    for w in &mut it {
        s = s.wrapping_add(u64::from_le_bytes(w.try_into().unwrap()));
    }
    let mut tail = [0u8; 8];
    tail[..it.remainder().len()].copy_from_slice(it.remainder());
    s.wrapping_add(u64::from_le_bytes(tail))
}

fn read_at(fd: i32, buf: &mut [u8], off: usize) -> usize {
    let n = unsafe { pread(fd, buf.as_mut_ptr(), buf.len(), off as i64) };
    assert!(n >= 0, "pread failed");
    n as usize
}

fn main() {
    let start = Instant::now();
    let args: Vec<String> = env::args().collect();
    let (path, threads, mode) = (&args[1], args[2].parse::<usize>().unwrap(), args[3].as_str());
    let buf_kib: usize = args.get(4).map_or(256, |s| s.parse().unwrap());
    let file = fs::File::open(path).expect("open");
    let fd = file.as_raw_fd();
    let len = file.metadata().unwrap().len() as usize;

    // Newline-aligned cuts found with small preads, so no mode touches the mapping here.
    let mut cuts = vec![0];
    let mut win = [0u8; 4096];
    for t in 1..threads {
        let mut at = (len * t / threads).max(cuts[t - 1]);
        'find: while at > 0 && at < len {
            let n = read_at(fd, &mut win, at - 1);
            for (k, &b) in win[..n].iter().enumerate() {
                if b == b'\n' {
                    at += k;
                    break 'find;
                }
            }
            at += n;
        }
        cuts.push(at.min(len));
    }
    cuts.push(len);

    let (mapped, dontneed, touch) = match mode {
        "mmap-touch" => (true, true, true),
        "mmap-sum" => (true, true, false),
        "mmap-nodontneed-touch" => (true, false, true),
        "mmap-nodontneed-sum" => (true, false, false),
        "mmap-populate-sum" => (true, true, false),
        "pread" => (false, false, false),
        _ => panic!("unknown mode {mode}"),
    };
    let t_map0 = start.elapsed().as_secs_f64();
    let d: &[u8] = if mapped {
        map_file(&file, len, if mode == "mmap-populate-sum" { 0x8000 } else { 0 })
    } else {
        &[]
    };
    let t_map1 = start.elapsed().as_secs_f64();
    let rows: Vec<(u64, String)> = thread::scope(|s| {
        let hs: Vec<_> = cuts
            .windows(2)
            .map(|w| {
                let (a, b) = (w[0], w[1]);
                s.spawn(move || {
                    let (t0, r0, c0) = (start.elapsed().as_secs_f64(), ru(1), cpu(3));
                    let mut sum = 0u64;
                    if !mapped {
                        let mut buf = vec![0u8; buf_kib << 10];
                        let mut off = a;
                        while off < b {
                            let want = buf.len().min(b - off);
                            let n = read_at(fd, &mut buf[..want], off);
                            assert!(n > 0);
                            sum = sum.wrapping_add(sum_words(&buf[..n]));
                            off += n;
                        }
                    } else if touch {
                        let mut p = a;
                        while p < b {
                            sum = sum.wrapping_add(unsafe { std::ptr::read_volatile(d.as_ptr().add(p)) } as u64);
                            p = (p & !4095) + 4096;
                        }
                    } else {
                        sum = sum_words(&d[a..b]);
                    }
                    let (t1, r1, c1) = (start.elapsed().as_secs_f64(), ru(1), cpu(3));
                    if dontneed {
                        let page = a & !4095;
                        unsafe { madvise(d.as_ptr().add(page), b - page, 4) };
                    }
                    let (t2, r2, c2) = (start.elapsed().as_secs_f64(), ru(1), cpu(3));
                    let line = format!(
                        "thread {a} bytes={} wall={:.9} cpu={:.9} user={:.6} sys={:.6} minflt={} majflt={} madv_wall={:.9} madv_cpu={:.9} madv_sys={:.6}",
                        b - a,
                        t1 - t0,
                        c1 - c0,
                        r1.user() - r0.user(),
                        r1.sys() - r0.sys(),
                        r1.minflt - r0.minflt,
                        r1.majflt - r0.majflt,
                        t2 - t1,
                        c2 - c1,
                        r2.sys() - r1.sys()
                    );
                    (sum, line)
                })
            })
            .collect();
        hs.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let t_end = start.elapsed().as_secs_f64();
    let checksum = rows.iter().fold(0u64, |s, r| s.wrapping_add(r.0));
    for (_, line) in &rows {
        eprintln!("{line}");
    }
    let (r, c) = (ru(0), cpu(2));
    let m = status_kb(&["VmHWM", "VmRSS", "RssAnon", "RssFile", "RssShmem"]);
    eprintln!(
        "probe {mode} threads={threads} buf_kib={buf_kib} map_wall={:.9} read_wall={:.9} total={t_end:.9} cpu={c:.9} utime={:.6} stime={:.6} minflt={} majflt={} VmHWM={} VmRSS={} RssAnon={} RssFile={} RssShmem={} checksum={checksum}",
        t_map1 - t_map0,
        t_end - t_map1,
        r.user(),
        r.sys(),
        r.minflt,
        r.majflt,
        m[0],
        m[1],
        m[2],
        m[3],
        m[4]
    );
}

// Paste this module above `fn main` in a copy of track-c/src/main.rs, then call
// `prof::install()` at the top of main, `let timer = prof::start();` first thing in each
// worker, `prof::stop(timer);` before the worker returns, and
// `prof::dump(&format!("{out}/prof.txt"));` after the output is written. Build with
// `debug = "line-tables-only"` in [profile.release]. Linux x86-64 glibc only.
/// Profiling only: each worker samples its own interrupted instruction address every 200 us.
mod prof {
    use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering::Relaxed};
    static N: AtomicUsize = AtomicUsize::new(0);
    static S: [AtomicU64; 1 << 21] = [const { AtomicU64::new(0) }; 1 << 21];
    #[repr(C)]
    struct SigAction { handler: usize, mask: [u64; 16], flags: i32, restorer: usize }
    #[repr(C)]
    struct SigEvent { value: u64, signo: i32, notify: i32, tid: i32, pad: [i32; 11] }
    #[repr(C)]
    struct ITimerSpec { interval: [i64; 2], value: [i64; 2] }
    extern "C" {
        fn sigaction(sig: i32, act: *const SigAction, old: *mut SigAction) -> i32;
        fn timer_create(clock: i32, sev: *const SigEvent, id: *mut usize) -> i32;
        fn timer_settime(id: usize, flags: i32, new: *const ITimerSpec, old: *mut ITimerSpec) -> i32;
        fn timer_delete(id: usize) -> i32;
        fn gettid() -> i32;
    }
    extern "C" fn on_prof(_sig: i32, _info: *mut u8, ctx: *mut u8) {
        let rip = unsafe { *(ctx.add(168) as *const u64) }; // uc_mcontext.gregs[REG_RIP]
        let i = N.fetch_add(1, Relaxed);
        if i < S.len() { S[i].store(rip, Relaxed); }
    }
    pub fn install() {
        let act = SigAction { handler: on_prof as usize, mask: [0; 16], flags: 4 | 0x10000000, restorer: 0 };
        unsafe { assert_eq!(sigaction(27, &act, std::ptr::null_mut()), 0) };
    }
    /// Starts this thread's timer; returns its id for `stop`.
    pub fn start() -> usize {
        let sev = SigEvent { value: 0, signo: 27, notify: 4, tid: unsafe { gettid() }, pad: [0; 11] };
        let mut id = 0;
        let t = ITimerSpec { interval: [0, 200_000], value: [0, 200_000] };
        unsafe {
            assert_eq!(timer_create(1, &sev, &mut id), 0);
            assert_eq!(timer_settime(id, 0, &t, std::ptr::null_mut()), 0);
        }
        id
    }
    pub fn stop(id: usize) { unsafe { timer_delete(id) }; }
    pub fn dump(path: &str) {
        let mut out = String::new();
        for l in std::fs::read_to_string("/proc/self/maps").unwrap().lines() { out += "M "; out += l; out += "\n"; }
        for i in 0..N.load(Relaxed).min(S.len()) { out += &format!("{:x}\n", S[i].load(Relaxed)); }
        std::fs::write(path, out).unwrap();
    }
}


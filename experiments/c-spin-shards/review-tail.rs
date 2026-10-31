use std::sync::{Arc,Barrier,Mutex};
use std::time::{Duration,Instant};
fn compare(workers:usize, spin:bool) {
    let iters=4000usize;
    let b=Arc::new(Barrier::new(workers));
    let m=Arc::new(Spin::<Vec<usize>>::default());
    let standard=Arc::new(Mutex::new(vec![0usize;workers]));
    *m.lock()=vec![0usize;workers];
    let t=Instant::now();
    let wait=thread::scope(|sc| {
        let mut handles=Vec::new();
        for id in 0..workers {
            let (m,standard,b)=(&m,&standard,&b);
            handles.push(sc.spawn(move|| {
                b.wait();let mut maxwait=Duration::ZERO;
                for _ in 0..iters {
                    let start=Instant::now();
                    if spin { let mut lock=m.lock(); maxwait=maxwait.max(start.elapsed());lock[id]+=1; }
                    else { let mut lock=standard.lock().unwrap();maxwait=maxwait.max(start.elapsed());lock[id]+=1; }
                }
                maxwait
            }));
        }
        handles.into_iter().map(|h|h.join().unwrap()).max().unwrap()
    });
    let elapsed=t.elapsed();
    let got=if spin {m.lock().clone()}else{standard.lock().unwrap().clone()};
    assert_eq!(got,vec![iters;workers]);
    println!("workers={workers} lock={} iterations={} elapsed_ms={:.3} max_observed_wait_ms={:.3}",if spin {"spin"} else {"std"},workers*iters,elapsed.as_secs_f64()*1000.,wait.as_secs_f64()*1000.);
}
fn main() {
    fn assert_send<T: Send>() {}
    assert_send::<Held<'static,u64>>();
    let m=Spin::<usize>::default();
    let old=std::panic::take_hook();std::panic::set_hook(Box::new(|_|{}));
    let r=std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {let mut g=m.lock();*g=41;panic!("guard unwind test")}));
    std::panic::set_hook(old); assert!(r.is_err()); assert_eq!(*m.lock(),41);
    println!("panic unwound; guard released and value retained");
    // A second thread must acquire after the owner panics while holding the lock.
    let lock=Arc::new(Spin::<usize>::default());
    let start=Arc::new(Barrier::new(2));
    let l=Arc::clone(&lock);let b=Arc::clone(&start);
    let old=std::panic::take_hook();std::panic::set_hook(Box::new(|_|{}));
    let failed=thread::spawn(move || {let mut g=l.lock(); *g=91;b.wait();panic!("cross-thread unwind")});
    start.wait(); assert_eq!(*lock.lock(),91);assert!(failed.join().is_err());
    std::panic::set_hook(old);
    println!("contending thread acquired after owner unwind");
    for workers in [1,2,7,32] {compare(workers,true);compare(workers,false);}
}

#!/usr/bin/env python3
"""make-profile.py base|cand SRC OUT: adds the profiling helpers of profile-helpers.rs and
breakdown prints (stderr, lines starting "bd" and "smaps") to a Track A main.rs: baseline.rs
(base) or candidate.rs (cand). Residency comes from /proc/self/pagemap per buffer and from
/proc/self/smaps per mapping class. Local profiling only."""
import os, sys

kind, src, out = sys.argv[1:4]
s = open(src).read()
helpers = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'profile-helpers.rs')).read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


thread_end = '''{
                    let x = 0u8;
                    let sp = &x as *const u8 as usize;
                    eprintln!("bd thread table_kb {} scratch_kb {} stack_kb {}",
                        res(&table.slots) + res(&table.arena), SCRATCH,
                        resident((sp - (512 << 10)) as *const u8, 528 << 10));
                }'''
if kind == 'base':
    rep('''                if barrier.wait().is_leader() {
                    let _ = plan.set(make_plan(shared, parsed));
                }''', '''                if barrier.wait().is_leader() {
                    let rec: u64 = parsed.iter().map(|p| p.lock().unwrap().iter().map(|r| res(&r.0) + res(&r.1)).sum::<u64>()).sum();
                    let len: usize = parsed.iter().map(|p| p.lock().unwrap().iter().map(|r| r.0.len() * 4).sum::<usize>()).sum();
                    let names: usize = shared.iter().map(|m| m.lock().unwrap().keys().map(|k| k.len() + 24 + 16).sum::<usize>()).sum();
                    smaps("after parse");
                    eprintln!("bd after_parse anon_kb {} records_resident_kb {rec} records_bytes_kb {} names_approx_kb {}", rss_anon(), len / 1024, names / 1024);
                    let _ = plan.set(make_plan(shared, parsed));
                }''')
    rep('''                    tx.send((h, summarize(h, records, order, names, &mut scratch))).unwrap();
                }''', '''                    tx.send((h, summarize(h, records, order, names, &mut scratch))).unwrap();
                }
                ''' + thread_end.replace('table_kb {} ', '').replace('res(&table.slots) + res(&table.arena), ', ''))
    rep('''        let (mut pending, mut written) = (vec![None; HOURS], 0);''', '''        let (mut pending, mut written) = (vec![None; HOURS], 0);
        let mut peak_pending = 0;''')
    rep('''            pending[h] = Some(out);''', '''            pending[h] = Some(out);
            let p: u64 = pending.iter().flatten().map(|o: &Vec<u8>| res(o)).sum();
            if p > peak_pending {
                peak_pending = p;
                eprintln!("bd pending_out_kb {p} anon_kb {}", rss_anon());
            }''')
    rep('''    let mut table = Table::default();''', '''    let mut table = Table::default();
        let x = 0u8;
        let sp = &x as *const u8 as usize;''')
    rep('''    unsafe { madvise(d.as_ptr().add(page), end - page, 4) }; // MADV_DONTNEED''', '''    unsafe { madvise(d.as_ptr().add(page), end - page, 4) }; // MADV_DONTNEED
    eprintln!("bd parse_thread table_kb {} stack_kb {}", res(&table.slots) + res(&table.arena), resident((sp - (512 << 10)) as *const u8, 528 << 10));''')
else:
    rep('''            } else if st.closed == HOURS {
                return;''', '''            } else if st.closed == HOURS {
                eprintln!("bd thread table_kb {}", res(&table.slots) + res(&table.arena));
                return;''')
    rep('''                let mut out = self.out.lock().unwrap();
                while out.0 < h {
                    out = self.turn.wait(out).unwrap();
                }''', '''                let mut out = self.out.lock().unwrap();
                while out.0 < h {
                    out = self.turn.wait(out).unwrap();
                }
                if h % 12 == 0 || h == HOURS - 1 {
                    let st = self.state.lock().unwrap();
                    let held: u64 = st.hours.iter().flatten().chain(st.jobs.iter().flat_map(|j| j.1.iter())).map(|r| res(&r.0) + res(&r.1)).sum();
                    let spare: u64 = self.spare.lock().unwrap().iter().map(res).sum();
                    let sc: u64 = st.scratch.iter().chain([&scratch]).map(|s| res(&s.counts) + res(&s.next) + res(&s.lat) + res(&s.out)).sum();
                    eprintln!("bd before_writing_hour {h} out_written_kb {} held_records_kb {held} spare_records_kb {spare} scratch_free_and_this_kb {sc} free_scratch {} open_hours {} queued {}",
                        out.1.as_ref().unwrap().metadata().unwrap().len() / 1024, st.scratch.len(), st.hours.iter().filter(|h| !h.is_empty()).count(), st.jobs.len());
                    drop(st);
                    smaps(&format!("before writing hour {h}"));
                }''')
s = s.replace('SCRATCH', 'res(&scratch.counts) + res(&scratch.next) + res(&scratch.lat)')
s += helpers
open(out, 'w').write(s)

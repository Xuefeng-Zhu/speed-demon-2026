#!/usr/bin/env python3
"""Reconstruct unselected reducer-prefetch variants from the exact saved baseline."""
from pathlib import Path
p=Path(__file__).resolve().parent
src=(p/'baseline.rs').read_text()
marker='struct Event { offset: u32, len: u16, group: u16, hash: u64 }'
old='''                for row in &parsed {
                    for &event in &row.1[bucket] {
                        let name = event_name(recs, event);'''
assert src.count(marker)==src.count(old)==1
for name,dist,cache in [('ahead1',1,False),('ahead4',4,False),('ahead8',8,False),('ahead4_cache',4,True)]:
 helper='''
/// Prefetch only addresses proven inside existing immutable slices; this is a hint.
#[inline(always)]
fn prefetch_future(recs: &[u8], cache: &[(u64, usize)], event: &Event) {
    #[cfg(target_arch = "x86_64")]
    {
        use std::arch::x86_64::{_mm_prefetch, _MM_HINT_T0};
        if let Some(byte) = recs.get(event.offset as usize) {
            unsafe { _mm_prefetch((byte as *const u8).cast(), _MM_HINT_T0); }
        }
'''
 if cache:
  helper+='''        if let Some(entry) = cache.get(event.hash as usize & (CACHE_SLOTS - 1)) {
            unsafe { _mm_prefetch((entry as *const (u64, usize)).cast(), _MM_HINT_T0); }
        }
'''
 else:
  helper+='''        let _ = cache;
'''
 helper+='''    }
    #[cfg(not(target_arch = "x86_64"))]
    let _ = (recs, cache, event);
}
'''
 new='''                for row in &parsed {
                    let events = &row.1[bucket];
                    for (event_index, &event) in events.iter().enumerate() {
                        if let Some(future) = events.get(event_index + LOOKAHEAD) {
                            prefetch_future(recs, &dict.cache, future);
                        }
                        let name = event_name(recs, event);'''.replace('LOOKAHEAD',str(dist))
 (p/f'{name}.rs').write_text(src.replace(marker,marker+helper).replace(old,new))
control='''                for row in &parsed {
                    let events = &row.1[bucket];
                    for (_event_index, &event) in events.iter().enumerate() {
                        let name = event_name(recs, event);'''
(p/'control.rs').write_text(src.replace(old,control))

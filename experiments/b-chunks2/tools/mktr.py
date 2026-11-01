#!/usr/bin/env python3
"""Transposed list offsets ("tr"), applied on top of baseline.rs or any candidate.

    python3 mktr.py in.rs out.rs

Instead of one offs array per chunk, scan_chunk stores the start of each of its lists in
column k of one shared table, starts[l * nchunks + k], so the answers read the starts
of list l in all chunks from one contiguous row (2 to 5 cache lines) instead of one
cache line per chunk. Memory is the same as the per-chunk offs arrays (nchunks rows of
nlist + 1 u32), allocated as zero pages before the index.
"""
import sys

src = open(sys.argv[1]).read()


def sub(old, new, count=1):
    global src
    assert src.count(old) == count, old
    src = src.replace(old, new)


sub('use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering::Relaxed};',
    'use std::sync::atomic::{AtomicU32, AtomicU64, AtomicUsize, Ordering::Relaxed};')
sub('    chunks: Vec<Chunk>,\n', '    chunks: Vec<Chunk>,\n    starts: Vec<u32>,\n')
sub('''/// A chunk's posting lists: list l has the ids first + docs[offs[l]..offs[l + 1]],
/// and its phrase matches as (query, id).
struct Chunk {
    first: u32,
    offs: Vec<u32>,
    docs: Vec<u16>,
    hits: Vec<(u32, u32)>,
}

impl Chunk {
    /// The chunk-local ids of the documents in list l.
    fn post(&self, l: usize) -> &[u16] {
        &self.docs[self.offs[l] as usize..self.offs[l + 1] as usize]
    }
}
''', '''/// A chunk's posting lists and its phrase matches as (query, id). With n chunks, list
/// l of chunk c has the ids first + docs[starts[l * n + c]..starts[(l + 1) * n + c]].
struct Chunk {
    first: u32,
    docs: Vec<u16>,
    hits: Vec<(u32, u32)>,
}

impl Plan {
    /// The chunk-local ids of the documents of chunk c in list l.
    fn post(&self, c: usize, l: usize) -> &[u16] {
        let n = self.chunks.len();
        &self.chunks[c].docs[self.starts[l * n + c] as usize..self.starts[l * n + n + c] as usize]
    }
}
''')
sub('fn scan_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan, rows: &[AtomicU64]) -> Chunk {',
    'fn scan_chunk(data: &[u8], lo: usize, hi: usize, plan: &Plan, rows: &[AtomicU64], col: impl Fn(usize, u32)) -> Chunk {')
sub('''    offs[nl] = w as u32;
    Chunk { first, offs, docs, hits }''', '''    offs[nl] = w as u32;
    offs[..=nl].iter().enumerate().for_each(|(l, &o)| col(l, o));
    Chunk { first, docs, hits }''')
sub('        let df: usize = chunks.iter().map(|c| c.post(t).len()).sum();\n',
    '        let df: usize = (0..chunks.len()).map(|c| plan.post(c, t).len()).sum();\n')
sub('''                let c = &chunks[chunks.partition_point(|c| c.first <= d) - 1];
                c.post(t).binary_search(&((d - c.first) as u16)).is_ok()''',
    '''                let c = chunks.partition_point(|c| c.first <= d) - 1;
                plan.post(c, t).binary_search(&((d - chunks[c].first) as u16)).is_ok()''')
sub('''        for c in chunks {
            tl.extend(c.post(t).iter().map(|&d| c.first + d as u32));''',
    '''        for (i, c) in chunks.iter().enumerate() {
            tl.extend(plan.post(i, t).iter().map(|&d| c.first + d as u32));''')
sub('    let next = AtomicUsize::new(0);\n', '''    let mut starts = std::mem::ManuallyDrop::new(vec![0u32; (plan.nlist + 1) * nchunks]);
    let starts: Vec<AtomicU32> =
        unsafe { Vec::from_raw_parts(starts.as_mut_ptr().cast(), starts.len(), starts.capacity()) };
    let next = AtomicUsize::new(0);
''')
sub('scan_chunk(data, cut(k), cut(k + 1), &plan, &rows)',
    'scan_chunk(data, cut(k), cut(k + 1), &plan, &rows, |l, o| starts[l * nchunks + k].store(o, Relaxed))')
sub('    plan.rows = rows.into_iter().map(AtomicU64::into_inner).collect();\n',
    '    plan.rows = rows.into_iter().map(AtomicU64::into_inner).collect();\n    plan.starts = starts.into_iter().map(AtomicU32::into_inner).collect();\n')
open(sys.argv[2], 'w').write(src)

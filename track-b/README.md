# Track B: Index

Frank Zhu, solo entry. Rust, standard library only. The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/b-index.md).

## Approach

The queries are part of the input, so the program reads them first and builds the index around them. Everything is in `src/main.rs`.

1. **Query-term dictionary.** Each term used by a query gets a dense id. It goes into an open-addressing table keyed by the token packed into 32 bytes (four `u64`). Tokens contain only `[a-z0-9]` bytes, so the key of a corpus token is built straight from the raw bytes with one OR (`| 0x20` lowercases `A`–`Z` and leaves digits unchanged). Corpus tokens that no query uses get no id and cost one probe.
2. **Phrase anchors.** A 512 KB sample at the start of the corpus is tokenized to estimate how common each term is. Each phrase is anchored on its rarest term. Which term is chosen affects only speed, never the answer.
3. **One parallel scan.** `docs.txt` is mapped with `mmap` (declared through `extern "C"`, so there is no crate) and split at line boundaries into one chunk per hardware thread. Each thread tokenizes its chunk exactly as the spec says (§2.2):
   - For BOOL terms it writes a stream of the distinct term ids in each document, then counting-sorts that stream into CSR posting lists (doc ids ascending).
   - Phrases are checked right there. The thread keeps the term-id sequence of the current document. At the end of the document it compares each anchor occurrence against the phrases anchored on that term, at the right offset. No positions are stored and no document is read twice.
   - Each thread hands its scanned 4 MB slices back to the kernel (`madvise(MADV_DONTNEED)`), so at any moment only a few pages of the corpus are resident.
4. **BOOL on bitmaps.** Each query runs strictly left to right on a dense bitmap with one bit per document (31 KB at full scale). A term with df > N/32 is turned into a shared bitmap the first time a query uses it (`OnceLock`). That makes `the OR of OR ...` a word-wise OR instead of 200,000 single-bit writes. Rarer terms set, clear or mask bits straight from their posting lists. Count, sum and the first ten ids come from one pass over the bitmap.
5. **Output.** Queries are split into four blocks per thread. Each block is formatted into its own string, and the strings are joined in order and written once.

## Correctness

The output is byte-identical (sha256) to the Python reference on seed 1 `sample`, seed 2 `sample` and seed 1 `full` (`f86973c2…4e80927`, the hash published in the spec). NOT is a set difference applied to the running result. Duplicate query lines each get their own output line. A phrase needs its terms at consecutive token positions inside one document.

## Dependencies

None. `std` only, plus `mmap` and `madvise` declared from libc, which `std` links anyway.

## With another 24 hours

- Lookups are memory-latency bound (about 40 ns each on the dev VM, even though only about 1 in 6 needs a second probe). Next steps: a small cache-resident front table for the few thousand most frequent terms, and batched lookups so several cache misses are in flight at once.
- Compress the posting lists, or skip lists for terms that become bitmaps anyway. This would cut memory below the current ~150 MB peak.
- Tune `DENSE`, `SLICE` and the sample size on the real box.

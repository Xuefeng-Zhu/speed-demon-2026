# Track A: Ingest (Rust, std only)

The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/a-ingest.md).

## Approach

One binary, `src/main.rs`, standard library only. It works in four steps.

1. **Map the file.** `requests.log` is mapped read-only with `mmap`, declared through a two-line `extern "C"` block. There is no `libc` crate. The input is already in the page cache, so the map copies nothing and adds nothing to our cgroup's memory. The map has 4 KiB of zeros after it: an anonymous region is reserved first and the file is mapped over its start. That way every 8-byte word load is safe, even on the last line. The file is cut into one newline-aligned chunk per hardware thread. Each thread asks for its own pages with `MADV_POPULATE_READ`, so the page tables fill in parallel and not in one serial `MAP_POPULATE`.
2. **Parse (parallel).** Each thread walks its chunk with fixed offsets and word-at-a-time (SWAR) scans:
   - The hour comes straight from six digits. 30 and 31 October and 1 and 2 November become day 0 to 3, so the hour index is `day*24 + HH - 18`, with no date library.
   - The method length is the first space in one 8-byte load, found without a branch.
   - The endpoint is scanned 8 bytes at a time for its closing space, and hashed on the way.
   - The latency is read with a branch-free SWAR conversion of up to 7 digits. A plain loop handles 8 to 10 digits, which are rare.
   - The status counts as 5xx when its first byte is `'5'`.

   Endpoints get dense ids from a small open-addressing table in each thread. A lookup checks the hash first, then compares the bytes word by word, so ids are always exact. Each line becomes one `u64` record, `id << 33 | is_5xx << 32 | latency`, added to that thread's bucket for its hour.
3. **Merge (serial, about 0.3 ms).** The per-thread tables go into one global table. The roughly 1,842 names are sorted once by bytes, which matches the spec's order where a prefix sorts first. An endpoint's rank in that sort is its output position, and each thread gets a map from its local id to the rank.
4. **Summarise (parallel, by hour).** Worker threads take whole hours from an atomic counter. For each hour a worker:
   - counts the records and errors per endpoint rank over every thread's bucket for that hour;
   - counting-sorts the latencies into a scratch array grouped by endpoint;
   - gets the nearest-rank p50, p95 and p99 with three `select_nth_unstable` calls. Each call works only on the part to the right of the last, so they cover about n, n/2 and n/20 values. Groups of 16 or fewer are simply sorted;
   - formats the lines with integer-only arithmetic, including `errors*1e6/count` floor.

   The main thread receives the finished hours over a channel and writes them in hour order while the other hours are still being worked on.

Nothing depends on the disorder in the file. Any line can sit in any chunk, and every hour reads every thread's bucket. Duplicate lines are separate records.

`SD_DATA`, `SD_OUT` and `SD_THREADS` override `/data`, `/out` and the thread count for local testing. The container uses the defaults.

## Correctness checks

The output is byte-identical (sha256) to the Python reference on:
- tiny and sample, seeds 1 and 2;
- full, seed 1: `495ca096…81cd3`, as in the spec;
- full, seed 2;
- the spec's worked example;
- an empty input, which gives a zero-byte output;
- an input whose size is an exact multiple of the page size;
- a 200k-line fuzz file with 3,000 random endpoints of 1 to 125 bytes, latencies of 0, 2³²−1 and 8 to 10 digits, and every hour.

These hold at 1, 2, 3, 7, 12, 64 and 200 threads.

## Dependencies

None. `[dependencies]` is empty, so D = 1. `mmap` and `madvise` are declared by hand.

## With another 24 hours

- Profile on the scoring box's i5-13500 with `perf`. All local numbers so far come from a shared 2-core arm64 machine.
- Try a 16- or 32-byte SSE2/AVX2 endpoint scan in place of the 8-byte SWAR loop. This is the hottest code.
- Try `-C target-cpu=native` and PGO with the allowlisted llvm-tools image.
- Compare 12 threads with 6 threads (P-cores only, no SMT siblings).
- Shrink the records to 6 bytes (`u32` latency and `u16` id) to lower peak memory from about 25 MB of anonymous memory.

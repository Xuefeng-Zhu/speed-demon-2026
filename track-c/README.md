# Track C: Join

The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/c-join.md).

## Approach

One std-only Rust file, `src/main.rs`, with no crates.

1. **Map, don't read.** Both files are `mmap`ed read-only through a two-line `extern "C"` declaration. The harness has already put `/data` in the page cache, so the 200 MB of records are never copied and never count toward the run's memory.
2. **Regions.** `regions.csv` becomes a `Vec<u16>` indexed by `region_id` and holding a group number. Countries get group numbers in order of first appearance. A hole or an id past the end of the table maps to `_UNMATCHED`, which is the last group.
3. **Split the CSV safely.** The records after the header are cut into one chunk per hardware thread. A cut can land inside a quoted note, so the threads first count the `"` bytes in their chunk, in parallel. By the grammar in spec 2.1, an LF is a record terminator exactly when an even number of quotes comes before it: quotes appear only in quoted fields, every complete quoted field holds an even number of them (open, close, and `""` pairs), and an LF can never fall between the two quotes of a `""` pair. So the prefix sum of the counts gives each cut its parity, and `sync` moves the cut forward to the byte after the first LF with even parity. That byte is a true record start. Both neighbouring threads compute the same boundary, so every record is parsed exactly once. This is an exact two-pass method, not a guess.
4. **Parse each chunk with a hand-written state machine.** A record start may carry a byte order mark, which is skipped. `number` reads `-?[0-9.]+`, ignoring the dot, so `-5.25` comes out as -525 integer cents with no floating point. It then steps over `,`, LF or CRLF. `field` reads an unquoted field up to the comma, or a quoted field up to the closing quote that is not part of a `""` pair, counting the pairs as it goes. Commas, LFs and BOM bytes inside quotes are plain data.
5. **Never unescape.** The byte length of a value is its raw length minus the number of `""` pairs. For counting distinct names, the raw bytes between the quotes serve as the key, because escaping is one-to-one, and an unquoted name (which cannot contain a quote) is byte-identical to its quoted form. `""` and an empty unquoted field both give the empty key.
6. **Distinct names, shared and exact.** All threads share one name dictionary, split into 256 mutex shards chosen by the name's hash. Each shard is aligned to 128 bytes, so no two locks share a cache line. It maps a name (copied into a small `Box`, so lookups stay in a few MB of cache-friendly heap instead of jumping around the 200 MB file) to a row holding one bit per group. The thread that sets a group's bit for a name counts it as a new distinct name for that group. Because this happens under the shard lock, the total is exact, and nothing has to be merged at the end.
7. **Aggregate per thread, merge at the end.** Each thread keeps `[count, id_sum, amount_sum, amount_min, amount_max, names_distinct, name_bytes, note_bytes]` per group. One `merge` function folds a record into its group, and a thread's totals into the final line. Lines are formatted, sorted (key bytes, then a space, so this is key order), and written once.

The hash is a small FxHash-style hasher, eight bytes per step. It replaces SipHash, which cost about 15% more CPU in the hot loop.

## Correctness

- Byte-identical to the reference on seed 1 `full`, seed 1/2/3 `sample` and seed 7 `tiny`. Seed 1 `full` gives `d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536`, and seed 1 `sample` gives `9035fed36823232dd41ae2d1b9d6d21aa7c73f49d8e95647e953a89d5ebe9a66`.
- Also checked against the reference on hand-written inputs, each run with 1, 2, 3, 5, 8, 12, 64 and 500 threads: the spec's worked example, no final terminator, unquoted non-empty names, runs of quotes (`""""`, `"""a"""`), a BOM inside quoted fields, and LF-heavy notes. 500 threads means more chunks than records.

## Dependencies

None (`dependency_count = 0`). `.cargo/config.toml` sets `target-cpu=x86-64-v3` (AVX2, which the i5-13500 has) only when building for x86-64.

## With another 24 hours

- Replace the mutex shards with a lock-free open-addressing table (CAS on 64-bit slots), so a lookup that finds its name never writes a shared cache line.
- Keep short names inline in the table slot, which removes the last pointer chase per record.
- Use a SIMD (SSE2/AVX2) quote/comma/LF scanner in place of the byte loops in `field` and `sync`.
- Shrink the memory peak (now about 12 MB of heap, mostly the name dictionary) toward the 50x memory cap.

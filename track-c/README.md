# Track C: Join

The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/c-join.md).

## Approach

One std-only Rust file, `src/main.rs`, with no crates.

1. **Map, don't read.** Both files are mapped read-only; mapping failures are checked before the resulting slices are used. The harness prewarms `/data` into the page cache, and measured cgroup memory depends on the kernel's accounting of mapped pages.
2. **Regions.** `regions.csv` becomes a `Vec<u16>` indexed by `region_id` and holding a group number. Countries get group numbers in order of first appearance. A hole or an id past the end of the table maps to `_UNMATCHED`, which is the last group.
3. **Split the CSV safely.** The records after the header are divided into line-aligned chunks. Each interior cut moves forward to the byte after the next CRLF. Spec §2.2 explicitly permits relying on its guarantee for every generated seed, including holdout: CR appears only in an outside-record CRLF terminator and the final record ends in CRLF. Bare LF may occur inside a quoted note or as a record terminator and is not used to synchronize. Multiple cuts can collapse to the same boundary. This relies on §2.2 and is not a general parser for the broader §2.1 grammar alone.
4. **Parse each chunk with a hand-written state machine.** A record start may carry a byte order mark, which is skipped. `number` reads `-?[0-9.]+`, ignoring the dot, so `-5.25` comes out as -525 integer cents with no floating point. It then steps over `,`, LF or CRLF. `field` reads an unquoted field up to the comma, or a quoted field up to the closing quote that is not part of a `""` pair, counting the pairs as it goes. Commas, LFs and BOM bytes inside quotes are plain data.
5. **Never unescape.** The byte length of a value is its raw length minus the number of `""` pairs. For counting distinct names, the raw bytes between the quotes serve as the key, because escaping is one-to-one, and an unquoted name (which cannot contain a quote) is byte-identical to its quoted form. `""` and an empty unquoted field both give the empty key.
6. **Distinct names, shared and exact.** All threads share a name dictionary split into 1,024 mutex shards chosen by the name's hash. Each shard maps a copied name to a row holding one bit per group. Each name/group update takes its shard lock; the worker that first sets the bit records one distinct name, and summing worker-local counts gives the exact total.
7. **Aggregate per thread, merge at the end.** Each thread keeps `[count, id_sum, amount_sum, amount_min, amount_max, names_distinct, name_bytes, note_bytes]` per group. One `merge` function folds a record into its group, and a thread's totals into the final line. Lines are formatted, sorted (key bytes, then a space, so this is key order), and written once.

The hash is a small FxHash-style hasher, eight bytes per step. It replaces SipHash, which cost about 15% more CPU in the hot loop.

## Correctness

The checked-mapping variant was compared with the official reference on generated and adversarial cases, including quote-boundary and forced-hash-collision tests. Native x86 tests of a disposable dataset dropped its file cache and confirmed zero resident pages before each of three runs; each cold run produced the correct full hash. A reported SIGBUS in the original PR was not reproduced, and the report did not include an environment or reproduction steps. Checking `MAP_FAILED` does not prevent a SIGBUS after a successful mapping.

- Byte-identical to the reference on seed 1 `full`, seed 1/2/3 `sample` and seed 7 `tiny`. Seed 1 `full` gives `d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536`, and seed 1 `sample` gives `9035fed36823232dd41ae2d1b9d6d21aa7c73f49d8e95647e953a89d5ebe9a66`.
- The CRLF-boundary implementation was checked on generated and adversarial §2.2-compatible inputs, including quoted bare LFs, BOMs, collapsed cuts and long records. Tests of the older quote-parity implementation on broader §2.1 inputs do not establish support for those inputs in the current implementation.

## Dependencies

None (`dependency_count = 0`). `.cargo/config.toml` sets `target-cpu=x86-64-v3` (AVX2, which the i5-13500 has) only when building for x86-64.

## With another 24 hours

- Replace the mutex shards with a lock-free open-addressing table (CAS on 64-bit slots), so a lookup that finds its name never writes a shared cache line.
- Keep short names inline in the table slot, which removes the last pointer chase per record.
- Use a SIMD (SSE2/AVX2) quote/comma/LF scanner in place of the byte loops in `field` and `sync`.
- Shrink the memory peak (now about 12 MB of heap, mostly the name dictionary) toward the 50x memory cap.

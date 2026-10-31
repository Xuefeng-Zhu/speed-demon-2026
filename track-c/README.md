# Track C: Join

The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/c-join.md).

## Approach

One std-only Rust file, `src/main.rs`, with no crates.

1. **Map, don't read.** Both files are mapped read-only; mapping failures are checked before the resulting slices are used. The harness prewarms `/data` into the page cache, and measured cgroup memory depends on the kernel's accounting of mapped pages.
2. **Regions.** `regions.csv` becomes a byte table indexed by `region_id` and holding a group number, built by all workers in two passes over their share of the file: first to note which countries occur, then to store each region's group. Groups are numbered in country-code order, and group 0 is `_UNMATCHED`, which also covers holes and ids past the end of the table.
3. **Split the CSV safely.** The records after the header are divided into line-aligned chunks. Each interior cut moves forward to the byte after the next CRLF. Spec §2.2 explicitly permits relying on its guarantee for every generated seed, including holdout: CR appears only in an outside-record CRLF terminator and the final record ends in CRLF. Bare LF may occur inside a quoted note or as a record terminator and is not used to synchronize. Multiple cuts can collapse to the same boundary. This relies on §2.2 and is not a general parser for the broader §2.1 grammar alone.
4. **Parse 64 bytes at a time.** Workers claim chunks (64 per thread) from an atomic counter. For each 64-byte block, AVX2 compares give masks of quotes, commas and LFs; a prefix XOR of the quote mask marks bytes inside quotes, and the commas and LFs outside quotes are the field and record ends. A record start may carry a byte order mark, which is skipped. Numbers are read with SWAR from the eight bytes that end where the field ends; `-5.25` becomes -525 integer cents with no floating point.
5. **Never unescape.** The byte length of a value is its raw length minus the number of `""` pairs. For counting distinct names, the raw bytes between the quotes serve as the key, because escaping is one-to-one, and an unquoted name (which cannot contain a quote) is byte-identical to its quoted form. `""` and an empty unquoted field both give the empty key.
6. **Distinct names by hash, counted on first sight.** All workers share one open-addressing table of 64-bit name hashes (2^17 slots to start; the run restarts with a table four times larger if it passes 7/8 full). A name's id is its slot. Names are identified by hash, not compared byte for byte: two of about 10^5 names share a 64-bit hash with probability about 3e-10 per dataset. Each slot is five words, the hash then a 256-bit set of groups, so the lookup and the set update touch the same cache line or the next one. A worker that sees a (name, group) pair tests the bit and, if it is clear, sets it with `fetch_or`; the one worker that finds it clear counts the name for that group. The set's cache line is prefetched for writing eight records earlier.
7. **Aggregate per thread, merge at the end.** Each parsing thread keeps `[count, id_sum, amount_sum, amount_min, amount_max, names_distinct, name_bytes, note_bytes]` per group. One `merge` function folds records and thread totals. Groups are numbered in key order, so the output needs no sort, and is written once.

Each record is finished 16 records after it is parsed (a ring buffer), so the name slot and region entry it needs have time to load. Delimiters are found 64 bytes at a time with AVX2 compare masks and a prefix-XOR quote mask.

## Correctness

The checked-mapping variant was compared with the official reference on generated and adversarial cases, including quote-boundary and forced-hash-collision tests. Native x86 tests of a disposable dataset dropped its file cache and confirmed zero resident pages before each of three runs; each cold run produced the correct full hash. A reported SIGBUS in the original PR was not reproduced, and the report did not include an environment or reproduction steps. Checking `MAP_FAILED` does not prevent a SIGBUS after a successful mapping.

- Byte-identical to the reference on seed 1 `full`, seed 1/2/3 `sample` and seed 7 `tiny`. Seed 1 `full` gives `d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536`, and seed 1 `sample` gives `9035fed36823232dd41ae2d1b9d6d21aa7c73f49d8e95647e953a89d5ebe9a66`.
- The CRLF-boundary implementation was checked on generated and adversarial §2.2-compatible inputs, including quoted bare LFs, BOMs, collapsed cuts and long records. Tests of the older quote-parity implementation on broader §2.1 inputs do not establish support for those inputs in the current implementation.

## Dependencies

None (`dependency_count = 0`). `.cargo/config.toml` sets `target-cpu=x86-64-v3` (AVX2, which the i5-13500 has) only when building for x86-64.

## With another 24 hours

- Speed up the per-record field extraction, which is now about half of the CPU time.
- Investigate more compact dictionaries and faster scanning while measuring both wall time and cgroup peak on the scoring box.
- Continue holdout-oriented tests of long names, collision promotion and the large-file fallback. The full seed-1 practice at `5afd571` reported a 77,950,976-byte cgroup peak; that is a measurement for that run, not a worst-case bound.


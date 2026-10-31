# Track C: Join

The task, the input files and the exact output format are in the [spec](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/c-join.md).

## Approach

One std-only Rust file, `src/main.rs`, with no crates.

1. **Map, don't read.** Both files are mapped read-only; mapping failures are checked before the resulting slices are used. The harness prewarms `/data` into the page cache, and measured cgroup memory depends on the kernel's accounting of mapped pages.
2. **Regions.** `regions.csv` becomes a `Vec<u16>` indexed by `region_id` and holding a group number. Countries get group numbers in order of first appearance. A hole or an id past the end of the table maps to `_UNMATCHED`, which is the last group.
3. **Split the CSV safely.** The records after the header are divided into line-aligned chunks. Each interior cut moves forward to the byte after the next CRLF. Spec §2.2 explicitly permits relying on its guarantee for every generated seed, including holdout: CR appears only in an outside-record CRLF terminator and the final record ends in CRLF. Bare LF may occur inside a quoted note or as a record terminator and is not used to synchronize. Multiple cuts can collapse to the same boundary. This relies on §2.2 and is not a general parser for the broader §2.1 grammar alone.
4. **Parse with two independent chunk cursors per worker.** Each worker interleaves fields from two disjoint CRLF-aligned chunks and finishes either remaining tail sequentially. A hand-written state machine parses each record. A record start may carry a byte order mark, which is skipped. `number` reads `-?[0-9.]+`, ignoring the dot, so `-5.25` comes out as -525 integer cents with no floating point. It then steps over `,`, LF or CRLF. `field` reads an unquoted field up to the comma, or a quoted field up to the closing quote that is not part of a `""` pair, counting the pairs as it goes. Commas, LFs and BOM bytes inside quotes are plain data.
5. **Never unescape.** The byte length of a value is its raw length minus the number of `""` pairs. For counting distinct names, the raw bytes between the quotes serve as the key, because escaping is one-to-one, and an unquoted name (which cannot contain a quote) is byte-identical to its quoted form. `""` and an empty unquoted field both give the empty key.
6. **Distinct names, owned and exact.** Parsing workers route compact name events by the full prehash to one owner. Each owner reduces its events into an exact name dictionary and one bit per group; it verifies name bytes even on a cache hit. A direct-mapped owner-local cache stores 32,768 `(hash, row)` entries. Collision chains longer than eight are promoted into a separately randomized exact-name map. A sentinel reparses names too long for the compact event. If the file or group count cannot be represented in the compact format, processing uses the original 1,024 mutex shards instead.
7. **Aggregate per thread, merge at the end.** Each parsing thread keeps `[count, id_sum, amount_sum, amount_min, amount_max, names_distinct, name_bytes, note_bytes]` per group; owner reductions supply the distinct counts. One `merge` function folds records and thread totals. Lines are formatted, sorted (key bytes, then a space, so this is key order), and written once.

The common quoted-name path fuses guarded eight-byte scanning with a streaming FxHash-style prehash. Full-hash collisions still route to the same owner, and exact byte comparison and salted collision promotion preserve correctness; equal hashes can concentrate work on one owner. On a supported target the delimiter scanner also uses guarded AVX2 loads.

## Correctness

The checked-mapping variant was compared with the official reference on generated and adversarial cases, including quote-boundary and forced-hash-collision tests. Native x86 tests of a disposable dataset dropped its file cache and confirmed zero resident pages before each of three runs; each cold run produced the correct full hash. A reported SIGBUS in the original PR was not reproduced, and the report did not include an environment or reproduction steps. Checking `MAP_FAILED` does not prevent a SIGBUS after a successful mapping.

- Byte-identical to the reference on seed 1 `full`, seed 1/2/3 `sample` and seed 7 `tiny`. Seed 1 `full` gives `d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536`, and seed 1 `sample` gives `9035fed36823232dd41ae2d1b9d6d21aa7c73f49d8e95647e953a89d5ebe9a66`.
- The CRLF-boundary implementation was checked on generated and adversarial §2.2-compatible inputs, including quoted bare LFs, BOMs, collapsed cuts and long records. Tests of the older quote-parity implementation on broader §2.1 inputs do not establish support for those inputs in the current implementation.

## Dependencies

None (`dependency_count = 0`). `.cargo/config.toml` sets `target-cpu=x86-64-v3` (AVX2, which the i5-13500 has) only when building for x86-64.

## With another 24 hours

- Reduce event traffic or imbalance between owner reductions without compromising exact collision handling.
- Investigate more compact dictionaries and faster scanning while measuring both wall time and cgroup peak on the scoring box.
- Continue holdout-oriented tests of long names, collision promotion and the large-file fallback. The full seed-1 practice at `5afd571` reported a 77,950,976-byte cgroup peak; that is a measurement for that run, not a worst-case bound.

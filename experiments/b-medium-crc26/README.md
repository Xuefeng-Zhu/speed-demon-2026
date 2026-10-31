# B guarded medium-token CRC rebase — unselected

Baseline is exact current B source SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`; candidate SHA-256 `28869a79d0ff162828095d3222e2f32c1c78f554ad1ef2097b941ce304f2ff76`. This rebases the prior guarded `b-crc-medium` onto current source. The trial builds a query-derived table for 9–16-byte terms and uses chained SSE4.2 CRC32C and exact two-word equality. If a trial insertion probes more than 32 entries or any occupied cyclic run exceeds 64, it discards the trial and uses the original generic exact table. Generic targets and all other lengths retain original logic. The thresholds bound trial insertion probes and occupied-run length, not table allocation or the original table's worst-case collision behavior. The trial allocates the next power of two at least twice the number of medium query keys.

Independent static review found no concrete defect; actual Linux SSE4.2 execution and performance are untested. With ARM software CRC emulation, `run-property.py` and `run-review.py` passed normal/forced collision, 300k random CRC pairs, 96,874 key/case/padding/alignment checks, and insertion/cyclic-run acceptance boundaries. Normal and forced-emulation builds each passed 40 mixed official-reference corpora. Normal emulation additionally passed duplicate/overlap, >1 MiB/shard-boundary cases and 250,000-document/19,000 duplicate phrase stress. Its full public seed-1 output matched `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`. These are not actual x86 guard tests, official cgroup measurement or performance evidence.

On an x86-64-v3 Linux VM with official full seed data already available, serialize the following, run from archive root, and do not run Docker on Mac. Verify CPU features before executing `--x86-v3`. `run-property.py` demands the Linux protected-page test actually run.

```sh
python3 experiments/b-medium-crc26/run-property.py --x86-v3
python3 experiments/b-medium-crc26/run-review.py --x86-v3
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-medium-crc26/baseline.rs -o /tmp/b-medium26-base
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/b-medium-crc26/candidate.rs -o /tmp/b-medium26-candidate
python3 experiments/b-avx2-token/alignment.py /tmp/b-medium26-candidate official/reference/b_index.py
export B_RUST_BINARY=/tmp/b-medium26-candidate
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-medium26-base --candidate /tmp/b-medium26-candidate --data /path/to/full-b --runs 15 --report /tmp/b-medium26-first.json
python3 experiments/b-rust-lengthhash/compare.py --baseline /tmp/b-medium26-base --candidate /tmp/b-medium26-candidate --data /path/to/full-b --runs 15 --report /tmp/b-medium26-repeat.json
```

The selected build uses PGO; non-PGO native screens do not establish a PGO win. If the native candidate is promising, retrain matching PGO on independently generated inputs, run reference and guard suites on the final binary, and compare actual official practice. Preserve memory/collision fallback and count source size. Full input, binaries, profiles, credentials and cached answers are not included. Process RSS is not parent-cgroup memory.

Parent-run dot VM compared separately trained, matched Rust/LLVM PGO builds of this exact candidate and baseline using the official seed-2 sample generator. Two paired x86 batches measured 9.8% and 8.5% lower wall and 7.6% and 8.3% lower CPU; median native RSS rose about 1–2%. Across this and D window, 216 full hashes and alternates, actual SSE4.2/AVX2 guard-page tests, natural collision fallback and queue-oracle checks passed. Native process RSS is not official parent-cgroup memory; the exact CRC+PGO build is being sent for official practice.

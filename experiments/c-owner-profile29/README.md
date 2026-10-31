# C owner-cache diagnostic — not a performance candidate

`baseline.rs` is exact selected C SHA-256 `8249f318e26050cc1a12f2be091344bf431ceb862665a3312bb29a92e140057d`. `profile.rs` SHA-256 `080022c21b0a263ca7977c4e6171ece89f46a002696cf1c2b4bfc519cc1ed43f` changes only the compact owner dictionary: counters for exact name-cache hits and misses and aggregate entries/promoted full hashes; per-worker totals print after the parallel reduction. Program output is unchanged. Instrumentation adds writes and logging, changes object layout and execution, and is not suitable for timing, CPU, cgroup or official scoring. The noncompact >4 GiB/group fallback remains intact but emits no diagnostics, so the runner refuses it.

One locally compiled native ARM `-O -C lto=fat -C codegen-units=1 -C panic=abort` execution against full public seed 1 passed the published output hash. Eight reported workers totaled 3,072,616 hits, 247,384 misses, 3,320,000 events, 100,520 exact-name rows and zero promoted full-hash chains. The output summed to 2,980,424 distinct (country,name) pairs. Thus this one instrumented run had 92.55% cache hits and 89.77% distinct pairs per event. Name/cache distribution, collisions, groups and worker partitioning can differ on hidden inputs; these observations neither guarantee target performance nor prove correctness. Large-file fallback and x86 were not exercised by this ARM run.

To reproduce on x86-64-v3 Linux without competing benchmarks, provide full seed-1 input independently; no data, credentials or output are included:

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-owner-profile29/profile.rs -o /tmp/c-owner-profile29
python3 experiments/c-owner-profile29/run.py /tmp/c-owner-profile29 /path/to/full-c --runs 3
```

The runner verifies the published full-seed output hash every time, checks diagnostic lines exist and reports per-run counts only. No Docker or system changes are required. Do not treat these counters as instruction timing or whole-cgroup memory, and do not assume 8 GiB holdout safety.

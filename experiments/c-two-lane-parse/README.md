# Track C interleaved two-lane parsing (unselected)

This isolated candidate is based on the exact selected dynamic-owner implementation `baseline.rs` SHA-256 `bcd4d7715bffd8a3dc062cad6e7aa0886a96d659fcc9170735c4d4d123f67eae`. Candidate `candidate.rs` SHA-256 `8249f318e26050cc1a12f2be091344bf431ceb862665a3312bb29a92e140057d`. No selected code is changed.

For the compact-event path only, each of n workers receives two disjoint chunks among 2n CRLF-synchronized chunks. It interleaves the field parsing of one record from each chunk, then processes whichever chunk remains. It appends the same name events and sums the same aggregates; event order is not semantically significant for exact distinct-name group membership. Two chunks can collapse onto the same boundary, and either lane can be empty. The >4 GiB/group-limit mutex-shard fallback remains unchanged. This relies on the §2.2 generated-input CRLF guarantee, not the broader CSV grammar alone.

`reference.py --source ... --seeds 24` passed 120 mixed CSV reference comparisons at 1, 2, 3, 7 and 16 worker counts. Native shared-Mac ARM full seed-1 paired screens compiled with `rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort`: 15-pair median wall baseline/candidate was 0.067483/0.064266 s then 0.067282/0.064260 s, CPU 0.423797/0.398517 s then 0.424683/0.398771 s. Median native process RSS was 298,123,264/293,224,448 B then 297,533,440/293,847,040 B. All 64 measured and warmup runs matched the official output hash. Both batches randomized order with the same fixed seed; these observations are not x86, official scoring or cgroup measurements. Raw outputs are `arm-a.json` and `arm-b.json`.

`lane-coverage.py` instruments the exact candidate at build time, records every parsed ID and paired/scalar-tail counts, and passed 70 official-reference comparisons at 1/2/3/7/12 workers. It exercised paired loops, both scalar tails, embedded LFs, BOMs, collapsed cuts and a 100,000-byte record spanning several desired cuts; each input ID appeared exactly once. An initial 180,000-byte field made the Python reference fail its default 131,072-byte field limit, before comparing either binary. The rerun used 100,000 bytes, still above the 65,535 sentinel, and passed. This adjustment is a reference-tool limitation and does not imply a general name-length limit in the candidate.

`forced-collision.py` forces all three packed parser hash sites to zero and passed a 2,400-record reference comparison at each of the five worker counts, explicitly confirming exact-name map promotion and a 70,000-byte sentinel name. `forced-fallback.py` passed both forced file-length and group-limit fallback branches at those same worker counts, confirming each branch was actually taken. The representability `gate.py` and the `guard.py` protected-page field/hash checks also passed on native ARM. The lane, collision and fallback suites compile with overflow and debug assertions. The `--avx2` mode of `guard.py` and all three main suites requires actual Linux x86-64-v3 hardware. Independent static review found no concrete interval, tail, overflow or owner correctness defect under the §2.2 input contract and 12-worker target: synchronized intervals cover the input once even when cuts collapse, and each worker's two lanes and scalar tails retain separate cursors. Actual Linux/x86 guarded loads and performance, full >4 GiB parsing and official cgroup use remain untested; do not select on ARM timings alone.

For a serialized x86-64-v3 Linux check, first confirm hardware support, then run from the archive root:

```sh
python3 experiments/c-two-lane-parse/lane-coverage.py --avx2
python3 experiments/c-two-lane-parse/forced-collision.py --avx2
python3 experiments/c-two-lane-parse/forced-fallback.py --avx2
python3 experiments/c-two-lane-parse/guard.py --avx2
python3 experiments/c-two-lane-parse/gate.py
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-two-lane-parse/baseline.rs -o /tmp/c-two-lane-baseline
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 experiments/c-two-lane-parse/candidate.rs -o /tmp/c-two-lane-candidate
python3 experiments/c-two-lane-parse/compare.py --baseline /tmp/c-two-lane-baseline --variant /tmp/c-two-lane-candidate --data /path/to/full-c --runs 15 --report /tmp/c-two-lane-x86.json
```

Repeat the paired test in a separately recorded batch and verify every full-data hash. The comparator measures process RSS and CPU, not parent-cgroup memory. Generate data independently from the official generator; no data is shipped.

No dataset or credential is included. No Mac Docker was used.

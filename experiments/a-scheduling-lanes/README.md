# Track A scheduling and parser-lane screens (not selected)

All variants derive from the exact selected Track A source at `e88ee2c`, SHA-256 `9aa7eb44c30fbfc5b701ff9467d26b0a27e765520c5e766ef90d0ea6b04d85fc`. They are independent alternatives and have not been selected or independently reviewed for every valid input. The archived `.rs` files retain Linux's original anonymous-mapping flag; native macOS tests used temporary copies changing only that flag to Darwin's value. No Mac Docker was used.

- `persistent.rs` keeps parse workers alive across the global endpoint merge, then reuses them for the hour-summary phase through a barrier and immutable context. Twelve randomized measured full-seed pairs after two warmups matched the published hash; on a shared ARM Mac median wall was 0.04687 s versus 0.04606 s baseline, median CPU 0.19155 versus 0.19091 s. Ranges overlapped. Its synthetic empty/1k/100k/100k and 14 page-end tests also passed. The barrier-based prototype has not been subjected to independent failure-path review and is not recommended from this result.
- `dynamic.rs` divides the input into four times as many line-aligned ranges as workers and assigns them dynamically, while retaining one endpoint table and hour buffers per worker. Sixteen randomized measured full-seed pairs after two warmups matched the published hash; median wall was 0.04698 s versus 0.04800 s baseline, CPU 0.20175 versus 0.19929 s. Ranges overlapped substantially, and it adds more `madvise` calls. Empty/1k/100k/100k synthetic cases, 14 page-end tests and the 132,624-group latency grid at 1/2/6/12/64 workers passed. The small noisy difference does not establish a target win.
- `lanes.rs` divides each parser's range into four complete-line subranges and interleaves one record per lane into the same local table. Twelve randomized measured full-seed pairs after two warmups matched the published hash; median wall was 0.04077 s versus 0.03825 s baseline, CPU 0.19221 versus 0.19158 s. Synthetic empty/1k/100k/100k and 14 page-end tests passed; broader adversarial review was not run because the local screen lost.

All timings are native shared-host ARM screens at 12 workers, not scoring-box x86 or official cgroup results; process RSS includes mapped input and samples may be affected by concurrent load. JSON files retain all samples including warmups. No data or cached answers are included. The selected source remains unchanged.

`profile.rs` adds a timing print around each static parse chunk. Eight hash-verified runs on the shared host are in `profile-mac-arm.json`; the first was cold. In seven warm instrumented runs, chunk durations varied roughly 9.8–22.9 ms. This can reflect hybrid cores and contention as well as input imbalance, and instrumentation perturbs timing; it does not prove an official-box straggler.

To repeat a target comparison, compile `baseline.rs` and one variant with identical release flags and CPU target, generate the official full seed-1 input separately, then run:

```sh
python3 experiments/a-scheduling-lanes/compare.py --baseline /path/to/baseline --candidate /path/to/candidate --data /path/to/full-a --report /tmp/a-scheduling.json --workers 12 --runs 12
```

The comparator randomizes order, warms up, uses fresh output directories, verifies the full output hash and records native wall/CPU/process peak RSS. Process RSS is not the official cgroup peak. Before any selection, repeat with serialized x86 workloads, separate warmed-cgroup memory measurement, independent review, alternate-reference tests and the official board. Run `track-a-verification/test.py --binary /path/to/candidate --io directories` and `page_end_test.py`/`latency_grid_test.py` as appropriate.

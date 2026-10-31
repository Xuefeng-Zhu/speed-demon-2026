# Track B: Index

This C++17 implementation reads the queries first and indexes only terms they use. A buffered `pread` scan finds document boundaries; six workers tokenize disjoint, contiguous document ranges into local postings, which are merged in ascending document ID order. A second worker pool evaluates queries into their original positions before ordered output. Boolean operators retain strict left-to-right semantics; phrase queries scan token sequences for exact adjacency. There are no non-standard runtime dependencies. The Docker build uses `-pthread` and pinned allowlisted images.

On a shared native x86 dot VM, the selected streaming candidate's full-seed median was 1.445 s versus 5.750 s for the previous selected candidate, with process peak RSS about 470 versus 337 MiB. All full hashes and alternate-reference cases in that comparison passed. These are local results, not official board time or cgroup memory; see `experiments/dot-vm.md`. The prior serial candidate is retained in `experiments/b-serial.cpp`.

The candidate passed the restricted ARM Linux Docker full-data hash check and fresh tiny reference cases, a 1,000-query edge fixture, and a test placing 32-byte tokens across six 1 MiB read boundaries. To reproduce the fixtures from the repository root:

```sh
python3 experiments/b-stream-boundary.py
python3 experiments/b-edge-fixture.py /tmp/b-stream-boundary-review official/reference/b_index.py
```

The first live-board practice measurement for the f45 source is recorded in `PERF.md`; final hidden-seed scoring remains outstanding.

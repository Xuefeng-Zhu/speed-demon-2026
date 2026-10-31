# Track B common-anchor stress

This is a synthetic grammar-valid workload, **not** an official benchmark or a
sample of the published generator distribution. Every document contains ten
repetitions of the eight tokens `a b c d e f g h`. There are 19,000 distinct
eight-token phrase queries and 31,000 copies of `BOOL a`. The current selected
implementation assigns 10,000 of the distinct phrases to the common `a b`
anchor. The script independently computes the matching windows and verifies
every output byte, including document counts, sums, and smallest ten IDs.

From the repository root, compile the two implementations and run a small
reference-backed check:

```sh
c++ -O3 -std=c++17 -pthread track-b/main.cpp -o /tmp/speed-b-selected
c++ -O3 -std=c++17 -pthread experiments/b-stream-2fc.cpp -o /tmp/speed-b-prior
python3 experiments/b-common-anchor.py /tmp/speed-b-selected \
  --baseline /tmp/speed-b-prior --documents 1 \
  --reference official/reference/b_index.py
```

For a larger check omit `--reference` and set `--documents 10000` or `100000`.
The reference is deliberately optional because it is slow on repeated common
terms. Inputs and outputs are created in a temporary directory and removed.

On the shared native macOS ARM host, individual runs produced:

| Documents | Selected wall time | Prior wall time | SHA-256 |
| --- | ---: | ---: | --- |
| 10,000 | 2.373 s | 2.345 s | `609946373dce71a0088861d3ea4b8bfd838a80b7af3f7f2d82739cbc5009f57d` |
| 100,000 | 15.22 s | not measured | `c4e92b071525853fb3f6ebe60b71bd6b77923d4aefa5754af02dc1d86485e6b7` |

Both 10,000-document implementations and the 100,000-document selected
implementation matched the independent oracle; the one-document case also
matched the official reference. The measurements include program startup,
were not controlled competition runs, and cannot predict holdout timing. The
large case used 38.85 seconds of total user CPU time. No candidate change was
made on this evidence alone.

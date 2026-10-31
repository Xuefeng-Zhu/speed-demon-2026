# D bounded forward warmup (unselected)

The exact packed-adjacency baseline `baseline.rs` has SHA-256 `793d13729fe4dabe2a1ed272fef78e19567456676ed8df52c075bc4ac33ebd05`. `build.py` generates variants that perform 1, 2, 4, 8, or 16 forward Dijkstra pops before initializing the reverse search. The forward heap, tentative distances and touched entries are retained; the tentative forward target distance, when present, initializes `best` before the original bidirectional continuation. No answers or input-derived state are precomputed.

For nonnegative directed weights, the bounded warmup preserves the forward Dijkstra invariant. A finite tentative target is the length of an actual path and hence a valid upper bound. After the reverse search starts, successful meets update that bound and the original two-frontier stopping rule applies. A self query returns immediately; an exhausted forward heap, an already settled target, zero-weight edges and stale entries follow the same cleanup path. This argument was independently reviewed but is not a formal proof of every implementation detail.

All six overflow-checked builds passed 80 random directed graphs and 16,000 Dijkstra-oracle queries per binary, plus 4,096 directed three-node graphs and 36,864 all-pairs reference answers per binary using the scripts in `../track-d-balanced-frontier/`. Each of 60 sample executions (one warmup and nine randomized rotations of all six binaries) produced the published seed-1 sample hash. They have not been tested on the full data or actual x86.

One randomized nine-rotation native ARM sample screen produced median wall seconds: baseline 0.020639, warm1 0.020350, warm2 0.020485, warm4 0.020676, warm8 0.020742 and warm16 0.020717. Median CPU seconds were 0.103998, 0.103362, 0.103855, 0.105458, 0.106100 and 0.104488 respectively. Full observations and source hashes are in `sample-screen.json`. The sample contains only one tenth of full nodes, edges and queries, timings are short and the host is shared. No substantial speed win is established; all variants remain unselected. Native process RSS is not official cgroup memory. No Docker was run on the Mac.

Reproduce by generating official D seed-1 sample data independently, then run:

```sh
python3 experiments/track-d-warm-forward/build.py
python3 experiments/track-d-warm-forward/screen.py --data /path/to/sample --build-dir /tmp/sd-warm-forward-build --report /tmp/sd-warm-forward.json --runs 9
```

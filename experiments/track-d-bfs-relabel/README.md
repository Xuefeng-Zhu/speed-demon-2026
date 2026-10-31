# Track D BFS graph relabeling (not selected)

This isolated experiment permutes nodes into undirected BFS order computed at runtime, rebuilds both directed CSR graphs with the new ids, and maps all query endpoints through the same complete permutation. It covers disconnected and isolated nodes. It uses no pregenerated graph information or answer data. `baseline.rs` is the exact selected balanced-frontier D source; `meeting.rs` is the relabel candidate.

Both candidates passed 80 randomized directed graph fixtures (16,000 Dijkstra-oracle queries each) and all 4,096 directed three-node graphs with edge weights absent, zero, one, or u32 max (36,864 all-pairs Floyd–Warshall checks). Every full seed-1 run including warmups matched the published SHA-256.

On the shared native macOS ARM host, three randomized measured full-data pairs after warmup had median wall **1.1540 s relabel vs 0.6799 s baseline** and median CPU 1.7816 s vs 2.3840 s, with maximum process RSS 558,841,856 vs 533,774,336 bytes. The relabel variant reduced measured CPU but its serial graph relabel/rebuild overhead made end-to-end wall time about 70% worse in this screen. The sample is small and other activity was present; native RSS is not cgroup memory, and this is not a target x86 result. `report.json` holds all runs including warmups.

For reproduction, generate full official D input independently and run `python3 experiments/track-d-bfs-relabel/compare.py --data /path/to/d-full --build-dir /tmp/d-bfs-build --report /tmp/d-bfs-report.json --runs 7`; compare with the independent oracle and exhaustive tests under `experiments/track-d-balanced-frontier/`. Any follow-up should profile/parallelize relabeling and include its complete preprocessing cost; no variant was promoted.

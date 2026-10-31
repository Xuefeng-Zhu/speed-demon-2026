# D radix occupancy mask using u64 (not selected)

This isolated candidate tracks occupied radix buckets 0–63 in a `u64`, checks bucket 64 separately, and updates the mask on push, redistribution, pop and clear. It retains the selected balanced-frontier search and exact termination. The 64th bucket fallback avoids relying solely on documented distance bounds. Source identities and all samples appear in `report.json`.

One warmup and seven randomized full-seed native ARM Mac pairs all matched the published output SHA-256. Candidate median wall was 0.276019 s versus baseline 0.264308 s, and median CPU was 1.929862 versus 1.847524 s. The shared host may have been contended; native RSS is not official cgroup memory, and these timings are not x86 or official scores. The slower candidate was not promoted. It also passed 80 random directed-graph fixtures / 16,000 independent oracle queries and 4,096 exhaustive three-node graphs / 36,864 all-pairs Floyd–Warshall queries.

Reproduce with independently generated full data: `python3 experiments/track-d-mask64/compare.py --data /path/to/full-d --build-dir /tmp/d-mask64 --report /tmp/d-mask64.json --runs 7`, then `python3 experiments/track-d-mask64/oracle.py /tmp/d-mask64/meeting` and `python3 experiments/track-d-mask64/exhaustive.py /tmp/d-mask64/meeting`. No Docker was used.

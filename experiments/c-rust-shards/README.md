# Rust C name-dictionary shard screen

Selected `track-c/src/main.rs` at commit `1b2da3d` uses 256 mutex shards. Three isolated variants changed only `(0..256)` to 64, 512 or 1024 and the corresponding hash mask `255` to `63`, `511` or `1023`. All 28 full seed-1 output hashes matched, including one warmup per variant. Six measured randomized-order runs per variant on a shared ARM macOS host produced:

| Shards | Median wall | Median CPU | Maximum process RSS |
| ---: | ---: | ---: | ---: |
| 64 | 0.4717 s | 1.3641 s | 226,197,504 B |
| 256 (selected) | 0.2716 s | 1.0728 s | 225,853,440 B |
| 512 | 0.2536 s | 1.0201 s | 225,886,208 B |
| 1024 | 0.2335 s | 1.0066 s | 226,131,968 B |

Raw samples are in `mac-arm-report.json`. Wall times overlapped substantially and other activity was present. Process RSS includes mapped pages and is not the warmed-cgroup measure; ARM is not the scoring CPU. The 1024-shard variant merits a matched x86/cgroup comparison and alternate-data checks, but is not selected from this noisy screen. The full-data hash alone is not broad correctness verification.

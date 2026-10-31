# A parsing and grouping screens (not selected)

Each source is an isolated variant of Track A at 4f2d688; the selected source was not changed. The included `.rs` files use the original Linux anonymous mmap flag. For the native ARM macOS timing only, temporary source copies used the Darwin MAP_ANON value 0x1000; all other code was unchanged. The `*-mac-arm.json` files contain every measured run, compiler and hashes. All paired full seed-1 outputs matched the published SHA-256. Other work was active; times are noisy native Mac observations, not official or x86 scores.

| Variant | Change | Runs per side | Median wall candidate / baseline | Median CPU candidate / baseline |
|---|---|---:|---:|---:|
| method | Select method length by first two bytes rather than scanning space | 9 | 0.05477 / 0.05267 s | 0.22899 / 0.22359 s |
| slice | Replace `same` word loop by standard byte-slice equality | 9 | 0.06941 / 0.06538 s | 0.23152 / 0.23203 s |
| short | Skip bytes comparison for endpoints <=8 bytes based on odd-multiplier hash injectivity at fixed length | 9 | 0.06304 / 0.05769 s | 0.22270 / 0.22640 s |
| memchr | Locate end of endpoint with libc memchr before hashing | 9 | 0.04999 / 0.04674 s | 0.22560 / 0.20926 s |
| group | Store parse-time local endpoint/hour latency groups in an arena, then gather for output | 7 | 0.05280 / 0.03977 s | 0.28136 / 0.19399 s |

None is selected. The short-key hash shortcut additionally depends on a mathematical injectivity invariant and was not subjected to the forced-constant-hash tests used for the current implementation. The group prototype matched the full hash but has not received independent boundary or adversarial review. `compare-template.py` compiles `baseline.rs` and `candidate.rs` in its own directory; copy the desired files to a temporary directory and choose identical flags, data and thread count when reproducing. Native process RSS is not official cgroup memory. No Docker was used.

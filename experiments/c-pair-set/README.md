# C direct distinct-pair sets — unselected prototype

Baseline is exact selected C direct-country parser SHA-256 `76497615f1abc0bf28a7b0d1d18030ebc263ddf8587d98c263ea5fc9e8840538`. Candidate replaces the per-name group bitset dictionary with sharded exact sets of `(name bytes, country group)` pairs; it computes a combined hash once but keeps full-byte and group equality. Space grows with distinct pairs, up to record count. Collision-heavy or clustered hash families may severely affect runtime; the prototype has not had adversarial or independent review.

Nine randomized full seed-1 ARM pairs plus warmups matched all 20 output hashes. Median candidate/baseline wall was 0.18906/0.13513 s, CPU 0.95763/0.73341 s, and peak process RSS ~427/226 MB. Raw samples are in `arm-report.json`. This shared-host native screen is slower and consumes substantially more memory; no target speed gain is established, no alternate tests were run, and the candidate is not selected. No Docker on Mac was used.

A second `reserve.rs` variant lazily reserves 4,096 pair slots per touched shard to avoid rehashing. Nine new full-data ARM pairs plus warmups also matched all hashes but remained slower: 0.14497/0.10348 s candidate/baseline wall and 0.93539/0.66727 s CPU, with ~495/226 MB maximum native RSS. Values are in `reserve-report.json`; this further screen does not justify selection or x86 testing.

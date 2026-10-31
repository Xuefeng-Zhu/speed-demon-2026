# C adaptive prefix-hash prototype — not selected

The experimental 4-, 8- and 16-byte prefix hash variants use exact byte equality and promote an inner shard map to full-name hashing after 48 distinct names share a weak routing hash. Each inner weak map has its own randomized seed. The selected source is unchanged.

Nine randomized full-seed ARM pairs per variant plus warmups matched 60 hashes. Candidate/baseline median wall for prefix 4, 8 and 16 was 0.10456/0.10422, 0.10053/0.10339 and 0.10271/0.10471 s; median CPU 0.66470/0.67063, 0.64074/0.66943 and 0.65369/0.67646 s. These shared-host measurements show no substantial gain and are not target scores.

An independent architectural review identified that promoting an inner map cannot redistribute a concentrated weak routing prefix: many distinct same-prefix/length names still contend on one shard. Long colliding names can make even 48 exact comparisons expensive; distinct weak hashes can also target the same shard. §2.2 does not guarantee a fixed name-length bound or uniform names. This prototype has no bound on these slowdowns and must not be promoted; a robust design would need byte/load budgets and a whole-run strong-routing restart. No alternate-data or concurrency tests were performed. No Mac Docker was used.

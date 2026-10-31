# B direct table for short tokens (not selected)

This isolated candidate adds an immutable 37³-entry direct-address table for all
one-to-three-byte alphanumeric query terms. Other terms use the existing exact
short-key hash table and all phrase summaries, Boolean semantics and bitmap caps
are unchanged. The zero-padded alphabet encoding is injective for documented
nonempty lowercase terms. Baseline is selected B source SHA-256
`322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`;
candidate is `a2791476e2797c8731a4a0798d23c5b18013ee09a3494be78dbafa150c53913f`.

Seven randomized full seed-1 native ARM pairs after warmup all matched the
published output hash. Median wall time was 0.539681 s candidate versus
0.519246 s baseline; median CPU was 1.764787 versus 1.707575 s. This shared-host
screen is not x86, cgroup or official scoring evidence. The candidate was not
selected because it was slower here. Raw samples are `mac-arm-report.json`.

A second direct table limited to one- and two-byte terms is `tiny2.rs`
(SHA-256 `92bc553937e179b21712669da808ebbe942157e95a2b96af26c1236f1698c1b7`).
Its seven randomized full-seed ARM pairs all matched the hash, but median wall
was 0.275290 s versus 0.260139 s baseline and CPU 1.650023 versus 1.577555 s.
It also passed `fixture.py`; raw timings are `mac-arm-tiny2.json`. Neither
screen supports promotion, and neither ran the x86 AVX2 path.

The candidate passed 40 mixed official-reference corpora, distributed top-ten
and overlap tests, >1 MiB read boundaries, and `fixture.py`, which compares all
47,988 possible one-to-three-byte terms plus Boolean and phrase queries to the
official reference. These tests ran the Mac scalar path, not the x86 AVX2 path.
For reproduction compile both sources with identical release flags and run
`python3 experiments/b-rust-lengthhash/compare.py --baseline /path/to/base
--candidate /path/to/candidate --data /path/to/full --runs 7 --report /tmp/b-tiny.json`;
run `python3 experiments/b-tiny-direct/fixture.py /path/to/candidate` for the
enumerated lookup fixture. No Docker was used.

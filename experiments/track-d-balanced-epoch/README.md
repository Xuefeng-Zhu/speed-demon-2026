# Balanced frontier with query epochs: x86 comparison

Baseline is current selected balanced-frontier D, SHA-256 `1022f4d9c9956b17fd054e96a26d09551eff61936a851edf88505e12e2b1946c`. `meeting.rs` is the balanced+epoch candidate, SHA-256 `dd933d2cadb0aee9685d6a22ab3f106151977c189d5a8129069d542e9d5b95e2`. The candidate stores 53-bit distance and 11-bit epoch, resetting on wrap; it does not clear touched vertices every query. It computes every answer from runtime input.

The official full bound n=1,740,512 and u32 weights gives n*(2^32-1)=7,475,442,116,555,040 < 2^53-1. Epoch zero is never active; every 2047 searches the arrays clear before reuse. Independent review found no defect. Native Mac tests: all 16 warmup/measured full hashes passed, 80 random graphs/16,000 queries per candidate, 4,096 exhaustive graphs/36,864 queries per candidate, forced-one-worker full-size maximum-weight chain, 6,000 repeated queries and 24,624 mixed queries crossing 12 epoch wraps. Seven shared ARM pairs had median 0.2729 s candidate vs 0.3124 s baseline, CPU 1.7405 vs 1.8271 s; these are not x86/cgroup/official scores.

Generate full seed-1 data independently using official/generators/d_traverse.py. On x86-64-v3, run serially without other benchmark load:

```sh
python3 compare.py --data /path/to/full-d --build-dir /tmp/sd-balanced-epoch-build --report /tmp/sd-balanced-epoch-x86.json --runs 9
python3 oracle.py /tmp/sd-balanced-epoch-build/baseline /tmp/sd-balanced-epoch-build/meeting
python3 exhaustive.py /tmp/sd-balanced-epoch-build/baseline /tmp/sd-balanced-epoch-build/meeting
python3 make_single.py
rustc --edition=2021 -C opt-level=3 -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3 /tmp/sd-balanced-epoch-single.rs -o /tmp/sd-balanced-epoch-single
python3 extremes.py /tmp/sd-balanced-epoch-single
python3 independent-wrap.py /tmp/sd-balanced-epoch-single
```

`compare.py` verifies each published full hash, randomizes order and records process RSS (Linux KiB, not cgroup memory); also measure official cgroup peak separately. No datasets, credentials, or generated answers are included.

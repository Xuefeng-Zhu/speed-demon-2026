# Track B frequent-term bitmap experiment

Baseline is selected Track B from commit 15c6be0476da8dccd0b9cfb8a17bc734552ce419 (also unchanged at e8e828a), SHA-256 `a47bc7aac61f03cea55337567ed1e7991aff067eddba3ddf4d3c0877a201ba2a`. Candidate `bitmap.cpp` SHA-256 `1c699d9deb863be5b955ac95272aca369d6f1999c12f5ce8923015b401a69524`. It retains exact bounded phrase summaries; it adds bitmaps for Boolean terms with at least 2048 matching documents, capped at 64 MiB total payload with postings fallback and evaluates qualifying Boolean expressions in strict input order. Existing vector operations handle other queries.

Pre-cap prototype native shared macOS ARM randomized six-pair full seed-1 medians: candidate 0.9237s vs baseline 0.9527s; CPU 3.7054s vs 4.0871s; peak process RSS 316,440,576 vs 274,841,600 bytes. All full outputs matched published hash; measurements were noisy and not official cgroup scoring. Rebenchmark on x86 with separately generated full data. Run these commands from the repository root (the standalone Library archive can instead use its root and omit the `experiments/b-frequent-bitmap/` prefixes):

```
python3 experiments/b-frequent-bitmap/compare.py --data /path/to/full-b --compiler g++ --runs 6 --report /tmp/b-bitmap-x86.json
c++ -std=c++17 -O3 -pthread experiments/b-frequent-bitmap/bitmap.cpp -o /tmp/b-bitmap
python3 experiments/b-frequent-bitmap/tests/dense.py /tmp/b-bitmap
python3 experiments/b-frequent-bitmap/tests/b-bounded-fuzz.py /tmp/b-bitmap
python3 experiments/b-frequent-bitmap/tests/b-bounded-boundary.py /tmp/b-bitmap
python3 experiments/b-frequent-bitmap/tests/b-bounded-shards.py /tmp/b-bitmap
python3 experiments/b-frequent-bitmap/tests/b-bounded-duplicates.py /tmp/b-bitmap
```

`dense.py` verifies reference equality for 63/64/65, 2047/2048/2049, 4095/4096/4097 and 8193 documents, including dense AND/OR/NOT and phrase cases. A test-only threshold-1 ASan/UBSan build also exercises bitmap logic on 40 random corpora and boundaries; a test-only eight-byte cap exercises fallback. The 250,000-document/19,000-duplicate-phrase stress passed. Compare peak cgroup memory separately; process RSS is not the board metric. Independent review passed normal capped, forced 8-byte cap, and ASan/UBSan forced 264-byte cap exercising mixed bitmap/postings paths; the 64 MiB limit excludes vector metadata, allocator and query scratch. This experiment is not yet selected.

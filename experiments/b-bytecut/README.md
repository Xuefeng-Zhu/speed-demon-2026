# Track B byte-range cuts, x86 comparison

Baseline is exact selected Track B source from commit e6e72aca0eef75416065d3af4933e9eb8d094fd5, SHA-256 `3667c8f167a95137ff535ddcded3ae8e383b2a655f8d58373e4f1b6ab70d9967`. Candidate SHA-256 `f8d41a2774acb76459fb76f96bcb364747491265aa168122b74f67bad8b18f99`. Both retain bounded phrase summaries. Candidate eliminates serial full-file newline scanning: it aligns nine byte cuts to newline by `pread`, and parses dense document IDs from each row. Cuts stay ordered, including repeated cuts through one long record.

No data or binaries are included. With separately generated public full seed-1 data and a C++17 compiler:

```
python3 compare.py --data /path/to/full-b --runs 7 --report /tmp/b-bytecut.json
c++ -std=c++17 -O2 -g -pthread -fsanitize=address,undefined candidate.cpp -o /tmp/b-bytecut-asan
python3 split_review.py /tmp/b-bytecut-asan official/reference/b_index.py
python3 exact_review.py /tmp/b-bytecut-asan official/reference/b_index.py
```

The comparator interleaves random order, checks every full output hash, and captures wall/CPU and per-process RSS. Linux RSS is KiB and is not official warmed-cgroup peak. Reference uses Python 3.11+; compile with the same target flags for fair comparisons. `bench.json` shows a shared, heavily contended macOS ARM screen: five paired medians 1.301 s candidate vs 1.840 s baseline and CPU 4.815 vs 5.263 s; all 12 hashes including warmups passed. x86 and official results are unknown.

Independent ASan/UBSan official-reference comparisons passed 70 cases including 0–100 docs, multiple byte cuts inside >1 MiB lines, UTF-8, duplicate/overlapping phrases, plus 33 exact line-start/LF/nearby byte cuts. Also passed 40 randomized reference corpora, >1MiB boundaries and distributed top-ten. Input follows published bounds and newline format. Candidate currently treats interrupted pread as failure, matching baseline. Extreme long records can make multiple cut scans redundant and unbalance workers; target performance must be measured. No Mac Docker was used.

## Token classification table (not selected)

`lut.cpp` replaces the ASCII classification/lowercasing comparisons with a 256-byte lookup table. All full seed-1 hashes passed in five measured randomized pairs plus one warmup. Under very heavy shared-host contention, medians were 2.633 s LUT versus 1.614 s byte-cut baseline, CPU 5.188 versus 4.860 s. `lut-bench.json` records all timings; the wide range precludes a clean target inference, but this screen does not support promotion. It has not had broad alternate-input review and was not in the VM package.

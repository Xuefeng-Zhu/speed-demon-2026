# Track C: Join

A standalone C++17 solution. It memory-maps the records input read-only, reads the two official files from `/data` and writes `/out/aggregates.txt`. The program uses a direct region-id lookup, parses CSV quoting and embedded newlines, collects views of canonical escaped names per country, then counts distinct names in a six-worker pool using per-country open-addressed tables with full-byte collision checks, and aggregates amounts in integer cents. It has no runtime dependencies beyond the standard library. It relies on the input generator guarantees in section 2.2 of the official spec, including region IDs in the lookup below one million, unquoted numeric fields, and valid records. It does not use a SQL or dataframe library.

## Reproduce local checks

From the workspace root, with Python 3.11+ and a C++17 compiler:

```sh
c++ -std=c++17 -O3 -DNDEBUG -pthread track-c/main.cpp -o /tmp/c-join
python3 official/generators/c_join.py --seed 1 --scale full --out /tmp/c-data
mkdir -p /tmp/c-out
/tmp/c-join /tmp/c-data /tmp/c-out
shasum -a 256 /tmp/c-out/aggregates.txt
```

The optional arguments are input and output directories; the defaults are `/data` and `/out`. Seed 1 full matched the published answer: `d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536`. Earlier implementations also matched the published sample hash and several fresh reference seeds. The current hash candidate passed fresh tiny seeds 2, 17 and 4242, sample seed 271828, and the VM alternate-reference campaign.

A two-pair interleaved local comparison on macOS ARM used the full seed-1 data. The prior name hash-set variant took 2.641 and 1.938 s with 352.0 and 354.6 MB peak RSS; the later serial sort-and-deduplicate variant took 1.142 and 0.709 s with 293.5 and 293.0 MB peak RSS. Other work was active, so these are exploratory measurements, not board scores. All four outputs matched the published full-data hash.

The prior heap-copy parallel candidate built offline and passed the restricted ARM Linux Docker full-data check in 0.84 s including container startup. It matched the published full-data hash and alternate-reference cases on a native x86 dot VM. Fresh tiny seeds 2, 17, 99 and 4242, sample seeds 13, 42 and 76543, and worked and extended parser fixtures also matched the official reference or expected output. Its median wall time was 0.4376 s versus 0.9685 s for the prior serial candidate; both reported 269276 KiB maximum RSS. These shared-VM numbers are not official board results. See `experiments/dot-vm.md`.

## Remaining checks

The first live-board practice measurement is recorded in `PERF.md`. Run additional generated seeds and record subsequent board run IDs there. Verify any change against the reference and measure on the board.


## Input mapping and scoring

The selected mapping variant matched the full hash in the pinned restricted ARM container and fresh reference/edge tests. In three alternating ARM Docker pairs with a separate prewarmer, cgroup peaks were approximately 75.6–76.1 MB versus 277.0–277.2 MB for the prior heap-copy version, with every hash correct. The host prewarms `/data` before the official run cgroup, so process RSS alone does not represent the official memory metric. Combined with a prior shared-x86 VM comparison (0.415 s mmap versus 0.462 s heap) and pinned formatted S 198 versus 167, those cross-machine observations suggest about 1.33× K, but are not an official board score. The prior heap-copy code is `experiments/c-heap-664.cpp`; local raw peaks are in `experiments/c-cgroup-report.json`.

On the live public-seed board, the mmap candidate at `2fc9110` passed all gates with T=0.527238 s, M=76,075,008 bytes, S=198 and K=6.548517 (`run-a9d0b9f55766`). The preceding heap-copy run reported T=0.526909 s, M=277,127,168 bytes, S=167 and K=5.188997. These are single practice runs, not final scores.


## Exact hash counting

The selected version replaces per-country sorting with open-addressed tables. Each slot stores an index into the immutable mapped input, and hash collisions are resolved by comparing complete encoded name bytes; the six workers own separate country tables. On a shared native x86 VM, this version had median 0.311 s versus 0.466 s for an independently verified f45 heap baseline. The comparison package's `selected` and `mmap` sources were identical, so comparisons inside it are against mmap, not f45. Local warmed ARM cgroup peaks for mmap+hash were around 79 MB versus 76 MB for mmap+sort, and pinned S was 213 versus 198. These cross-run and cross-machine measurements are not an official score. Full hash, alternate reference seeds, BOM/EOF cases, and a forced-all-hashes-collide ASan/UBSan build over 40 mixed corpora passed. The previous mmap+sort source is `experiments/c-mmap-2fc.cpp`.

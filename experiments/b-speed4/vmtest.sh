#!/bin/bash
# VM side: correctness suite for a Track B binary against the official reference.
# vmtest.sh /path/to/binary
set -u
B=$(readlink -f "$1")
T=~/kiro-b/tests
R=$T/repo
fail=0
check() { # name data_dir expected_file threads
  rm -rf /dev/shm/kbt-out && mkdir -p /dev/shm/kbt-out
  if ! SD_DATA=$2 SD_OUT=/dev/shm/kbt-out SD_THREADS=$4 timeout 120 "$B" 2>/dev/shm/kbt-err; then
    echo "FAIL $1 threads $4: exit"; head -3 /dev/shm/kbt-err; fail=1; return
  fi
  if ! cmp -s /dev/shm/kbt-out/results.txt "$3"; then echo "FAIL $1 threads $4: output differs"; fail=1; fi
}
# 1. Generated tiny and sample datasets, reference outputs cached.
for spec in tiny:2 tiny:17 tiny:99 tiny:4242 sample:13 sample:3; do
  scale=${spec%%:*}; seed=${spec##*:}
  d=$T/gen/$scale-$seed
  if [ ! -s $d/ref/results.txt ]; then
    mkdir -p $d/data $d/ref
    python3 ~/kiro-b/generator.py --seed $seed --scale $scale --out $d/data >/dev/null
    python3 $R/official/reference/b_index.py --data $d/data --out $d/ref >/dev/null
  fi
  for th in 1 2 7 12 16; do check "$scale-$seed" $d/data $d/ref/results.txt $th; done
done
echo "generated datasets done"
# 2. Edge fixtures with independent oracles (0 to 100,000 documents).
F=~/optimize-b-active-20261101/fixtures
for c in $(ls $F | grep '^n'); do
  n=$((10#${c#n}))
  for th in 2 12; do check "fixture-$c" $F/$c $F/$c/expected.results.txt $th; done
  [ $n -le 65536 ] && check "fixture-$c" $F/$c $F/$c/expected.results.txt 1
done
echo "fixtures done"
# 3. The team's randomized and boundary suites through the positional adapter.
cd $R
for th in 1 4 12; do
  for s in b-bounded-fuzz.py b-bounded-boundary.py b-bounded-shards.py b-bounded-duplicates.py b-bounded-randomized.py b-edge-fixture.py; do
    extra=; [ $s = b-edge-fixture.py ] && extra=$R/official/reference/b_index.py
    out=$(B_RUST_BINARY=$B SD_THREADS=$th timeout 900 python3 experiments/$s $R/experiments/b-rust-positional-adapter.py $extra 2>&1 | tail -1)
    case "$out" in PASS*|*pass*|*PASS*) ;; *) echo "FAIL $s threads $th: $out"; fail=1;; esac
  done
done
echo "suites done"
[ $fail = 0 ] && echo "ALL PASS" || echo "SOME FAILED"

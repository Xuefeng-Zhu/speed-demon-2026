#!/bin/bash
# dcheck.sh SRC.rs: Track D correctness suite on the VM, after experiments/track-d-reuse-spare43/checks.sh.
# Builds SRC with overflow checks and debug assertions, runs the team's oracle suites (default CPUs,
# then pinned to CPU 0 and CPUs 0-2), then compares a release build with the official reference on
# generated tiny and sample inputs. Prints ALL CHECKS PASSED or exits nonzero.
set -eu
export PATH=$HOME/.cargo/bin:$PATH
K=~/kiro-k2
SRC=$(readlink -f "$1")
W=$(mktemp -d /tmp/kk-dcheck-XXXX)
mkdir -p $W/root/track-d/src
cp -r $K/tracks/d/Cargo.toml $K/tracks/d/.cargo $W/root/track-d/
cp $K/tracks/d/Cargo.lock $W/root/track-d/ 2>/dev/null || true
cp "$SRC" $W/root/track-d/src/main.rs
cd $W/root/track-d
RUSTFLAGS="-C target-cpu=x86-64-v3 -C overflow-checks=yes -C debug-assertions=yes" CARGO_TARGET_DIR=$W/t-checked \
  cargo build --release --offline -q
BIN=$W/t-checked/release/solution
X=$K/experiments
echo "== checked build, CPUs 0-11"
taskset -c 0-11 python3 $X/track-d-balanced-frontier/oracle.py $BIN
taskset -c 0-11 python3 $X/track-d-balanced-frontier/exhaustive.py $BIN
taskset -c 0-11 python3 $X/track-d-coarse-radix33/same_bucket.py $BIN
taskset -c 0-11 python3 $X/track-d-u32-fallback/thresholds.py $BIN
taskset -c 0-11 python3 $X/track-d-packed32-adj/boundaries.py $BIN
taskset -c 0-11 python3 $X/track-d-balanced-frontier/extremes.py $BIN
for cpus in 0 0-2; do
  echo "== checked build, CPUs $cpus"
  taskset -c $cpus python3 $X/track-d-balanced-frontier/oracle.py $BIN
  taskset -c $cpus python3 $X/track-d-balanced-frontier/exhaustive.py $BIN
  taskset -c $cpus python3 $X/track-d-coarse-radix33/same_bucket.py $BIN
done
echo "== official reference, tiny seeds 2 17 4242"
python3 $X/differential.py --tracks d --seeds 2 17 4242 --candidate-root $W/root --official-root $K/official
echo "== official reference, sample seeds 2 7"
python3 $X/differential.py --tracks d --scale sample --seeds 2 7 --candidate-root $W/root --official-root $K/official
rm -rf $W
echo "ALL CHECKS PASSED"

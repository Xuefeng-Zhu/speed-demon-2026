#!/bin/sh
# Correctness checks for track-d/src/main.rs, run from the repository root with:
#   docker run --rm -v "$PWD":/repo:ro -v "$PWD/experiments/track-d-reuse-spare43":/t:ro \
#     rust:1-slim-trixie@sha256:1a939748a7cbab172de91a014e3804a97af1394a8c844faa67fce9401c4e40fb sh /t/checks.sh
# It needs network access once, to install python3. It builds Track D with overflow
# checks and debug assertions and runs the team's oracle suites, some pinned to 1 and
# 3 CPUs; then differential.py builds a normal release and compares it with the
# official reference on generated tiny and sample inputs.
set -eu
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq python3 >/dev/null 2>&1
python3 --version
mkdir -p /work/root
cp -r /repo/track-d /work/root/track-d
rm -rf /work/root/track-d/target
cd /work/root/track-d
RUSTFLAGS="-C overflow-checks=yes -C debug-assertions=yes" CARGO_TARGET_DIR=/work/t-checked \
  cargo build --release --offline -q
BIN=/work/t-checked/release/solution
X=/repo/experiments
echo "== checked build, default CPUs ($(nproc))"
python3 $X/track-d-balanced-frontier/oracle.py $BIN
python3 $X/track-d-balanced-frontier/exhaustive.py $BIN
python3 $X/track-d-coarse-radix33/same_bucket.py $BIN
python3 $X/track-d-u32-fallback/thresholds.py $BIN
python3 $X/track-d-packed32-adj/boundaries.py $BIN
python3 $X/track-d-balanced-frontier/extremes.py $BIN
for cpus in 0 0-2; do
  echo "== checked build, CPUs $cpus"
  taskset -c $cpus python3 $X/track-d-balanced-frontier/oracle.py $BIN
  taskset -c $cpus python3 $X/track-d-balanced-frontier/exhaustive.py $BIN
  taskset -c $cpus python3 $X/track-d-coarse-radix33/same_bucket.py $BIN
done
echo "== official reference, tiny seeds 2 17 4242"
python3 $X/differential.py --tracks d --seeds 2 17 4242 --candidate-root /work/root --official-root /repo/official
echo "== official reference, sample seeds 2 7"
python3 $X/differential.py --tracks d --scale sample --seeds 2 7 --candidate-root /work/root --official-root /repo/official
echo "ALL CHECKS PASSED"

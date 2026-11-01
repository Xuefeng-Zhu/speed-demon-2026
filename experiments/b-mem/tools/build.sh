#!/bin/sh
# build.sh <src.rs> <binname>: builds <src.rs> with track-b's Cargo.toml, Cargo.lock and
# .cargo/config.toml (x86-64-v3, release profile) in a scratch cargo project outside the repo
# ($D/mem/proj, created on first use), saves the binary as $D/bin/<binname>, prints warnings
# and the seed-1 results.txt hash prefix of one default run (expected f86973c210228141).
# Fails if the build fails. The binary is byte-identical to a build inside track-b/.
set -e
D=/projects/sandbox/.data; P=$D/mem/proj; R=/projects/sandbox/speed-demon-2026/track-b
if [ ! -f $P/Cargo.toml ]; then
  mkdir -p $P/src $P/.cargo && cp $R/Cargo.toml $R/Cargo.lock $P/ && cp $R/.cargo/config.toml $P/.cargo/
fi
mkdir -p $D/bin
cp "$1" $P/src/main.rs && touch $P/src/main.rs
rm -f $P/target/release/solution
if ! (cd $P && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release >$D/mem/build.log 2>&1); then
  grep -E "^(warning|error)" -A7 $D/mem/build.log; echo "BUILD FAILED: $1"; exit 1
fi
grep -E "^(warning|error)" -A7 $D/mem/build.log || true
cp $P/target/release/solution $D/bin/$2
o=$D/mem/out-$2; rm -rf $o; mkdir -p $o
SD_DATA=$D/speed-b-full SD_OUT=$o $D/bin/$2 2>$o/err; echo "$2 $(sha256sum $o/results.txt | cut -c1-16) bin $(sha256sum $D/bin/$2 | cut -c1-12)"

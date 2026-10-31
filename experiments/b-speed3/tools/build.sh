#!/bin/sh
# build.sh <src.rs> <binname>: builds with x86-64-v3 and saves to .data/bin/<binname>; restores main.rs
set -e
R=/projects/sandbox/speed-demon-2026; D=/projects/sandbox/.data
cp $R/track-b/src/main.rs $D/s3/main.rs.save
cp "$1" $R/track-b/src/main.rs && touch $R/track-b/src/main.rs
(cd $R/track-b && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release 2>&1 | grep -E "^(warning|error)" -A5 || true)
cp $R/track-b/target/release/solution $D/bin/$2
cp $D/s3/main.rs.save $R/track-b/src/main.rs
# quick hash check
o=$D/s3/out-$2; rm -rf $o; mkdir -p $o
SD_DATA=$D/speed-b-full SD_OUT=$o $D/bin/$2 2>$o/err; sha256sum $o/results.txt | cut -c1-16

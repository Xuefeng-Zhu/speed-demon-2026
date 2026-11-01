#!/bin/sh
# build.sh SRC NAME: build SRC as track B into /projects/sandbox/.data/bin/NAME
set -e
W=/projects/sandbox/.data/b2/bb
cp "$1" $W/src/main.rs
cd $W && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release -q
cp target/release/solution /projects/sandbox/.data/bin/$2

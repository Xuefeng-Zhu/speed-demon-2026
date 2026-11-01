#!/bin/sh
# build.sh SRC.rs NAME: builds SRC as Track C (native, same profile) in a scratch crate and
# copies the binary to /projects/sandbox/.data/bin/NAME.
set -e
C=/projects/sandbox/.data/cm/crate
cp "$1" "$C/src/main.rs"
(cd "$C" && RUSTFLAGS='-Ctarget-cpu=native' cargo build --release -q)
cp "$C/target/release/solution" "/projects/sandbox/.data/bin/$2"

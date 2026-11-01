#!/bin/sh
# build.sh SRC NAME: builds a Track A source file in a scratch copy of track-a and copies the
# binary to /projects/sandbox/.data/bin/NAME.
set -e
src=$(realpath "$1"); dir=/projects/sandbox/.data/a-mem-build
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
mkdir -p "$dir/src"
cp "$repo/track-a/Cargo.toml" "$repo/track-a/Cargo.lock" "$dir/"
cp -r "$repo/track-a/.cargo" "$dir/" 2>/dev/null || true
cp "$src" "$dir/src/main.rs"
(cd "$dir" && RUSTFLAGS='-Ctarget-cpu=native' cargo build --release -q)
cp "$dir/target/release/solution" "/projects/sandbox/.data/bin/$2"

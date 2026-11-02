#!/bin/bash
# VM side: build each named candidate from ~/kiro-b/src-<name>.rs, plain and PGO.
# The PGO steps copy track-b/Dockerfile: train on sample seed 2, merge, rebuild.
set -euo pipefail
source ~/.cargo/env
K=~/kiro-b
PD="$(rustc --print sysroot)/lib/rustlib/x86_64-unknown-linux-gnu/bin/llvm-profdata"
mkdir -p $K/bin
for n in "$@"; do
  d=$K/c/$n
  rm -rf $d && mkdir -p $d/src $d/.cargo
  cp $K/src-$n.rs $d/src/main.rs
  cat > $d/Cargo.toml <<'EOF'
[package]
name = "solution"
version = "0.1.0"
edition = "2021"
[dependencies]
[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
panic = "abort"
EOF
  ( cd $d
    CARGO_TARGET_DIR=$d/t-plain RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build -q --release --target x86_64-unknown-linux-gnu >$d/build.log 2>&1 || { tail -40 $d/build.log; exit 1; }
    cp $d/t-plain/x86_64-unknown-linux-gnu/release/solution $K/bin/$n
    rm -rf $d/pgo && mkdir -p $d/pgo/raw $d/pgo/out
    CARGO_TARGET_DIR=$d/t-inst RUSTFLAGS="-Ctarget-cpu=x86-64-v3 -Cprofile-generate=$d/pgo/raw" cargo build -q --release --target x86_64-unknown-linux-gnu >>$d/build.log 2>&1 || { tail -40 $d/build.log; exit 1; }
    SD_DATA=$K/train SD_OUT=$d/pgo/out LLVM_PROFILE_FILE="$d/pgo/raw/%m-%p.profraw" $d/t-inst/x86_64-unknown-linux-gnu/release/solution
    test -s $d/pgo/out/results.txt
    "$PD" merge -o $d/pgo/merged.profdata $d/pgo/raw/*.profraw
    CARGO_TARGET_DIR=$d/t-pgo RUSTFLAGS="-Ctarget-cpu=x86-64-v3 -Cprofile-use=$d/pgo/merged.profdata" cargo build -q --release --target x86_64-unknown-linux-gnu >>$d/build.log 2>&1 || { tail -40 $d/build.log; exit 1; }
    cp $d/t-pgo/x86_64-unknown-linux-gnu/release/solution $K/bin/$n-pgo
  )
  echo "built $n: $(sha256sum < $K/src-$n.rs | cut -c1-12)"
done

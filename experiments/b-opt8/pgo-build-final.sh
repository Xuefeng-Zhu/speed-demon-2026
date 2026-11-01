#!/bin/sh
set -eu
profdata="$(rustc --print sysroot)/lib/rustlib/x86_64-unknown-linux-gnu/bin/llvm-profdata"
for spec in remote:b-opt8/remote-lean-reuse final:b-opt8/candidate; do
    name=${spec%%:*}
    src=${spec#*:}
    root=/result/pgo-$name
    mkdir -p "$root/context/src" "$root/context/.cargo" "$root/raw" "$root/out"
    cp /work/track-b/Cargo.toml /work/track-b/Cargo.lock "$root/context/"
    cp /work/track-b/.cargo/config.toml "$root/context/.cargo/"
    cp /work/experiments/$src.rs "$root/context/src/main.rs"
    echo "PGO instrument $name"
    CARGO_TARGET_DIR="$root/instrumented" RUSTFLAGS="-Ctarget-cpu=x86-64-v3 -Cprofile-generate=$root/raw" cargo build --manifest-path "$root/context/Cargo.toml" --target x86_64-unknown-linux-gnu --release --offline
    SD_THREADS=12 SD_DATA=/result/training SD_OUT="$root/out" LLVM_PROFILE_FILE="$root/raw/%m-%p.profraw" "$root/instrumented/x86_64-unknown-linux-gnu/release/solution"
    "$profdata" merge -o "$root/merged.profdata" "$root"/raw/*.profraw
    "$profdata" show --counts "$root/merged.profdata"
    echo "PGO optimize $name"
    CARGO_TARGET_DIR="$root/optimized" RUSTFLAGS="-Ctarget-cpu=x86-64-v3 -Cprofile-use=$root/merged.profdata -Cllvm-args=-pgo-warn-missing-function" cargo build --manifest-path "$root/context/Cargo.toml" --target x86_64-unknown-linux-gnu --release --offline
    cp "$root/optimized/x86_64-unknown-linux-gnu/release/solution" /result/$name-pgo-x86
    sha256sum /result/$name-pgo-x86
 done

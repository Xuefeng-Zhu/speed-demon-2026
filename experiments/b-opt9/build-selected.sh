#!/bin/sh
# Pinned x86 Rust image; same context/flags and seed-2 sample for every source.
set -eu
repo=${1:-/work}
result=${2:-/result}
run=$result/opt9-selected-pgo
test ! -e "$run"
mkdir -p "$run/context/src" "$run/context/.cargo" "$run/default"
cp "$repo/track-b/Cargo.toml" "$repo/track-b/Cargo.lock" "$run/context/"
cp "$repo/track-b/.cargo/config.toml" "$run/context/.cargo/"
profdata="$(rustc --print sysroot)/lib/rustlib/x86_64-unknown-linux-gnu/bin/llvm-profdata"
printf 'name\tstart_s\tend_s\tcgroup_cumulative_peak_bytes\n' > "$run/builds.tsv"
for spec in baseline:b-opt9/baseline candidate:b-opt9/candidate; do
    name=${spec%%:*}
    src=${spec#*:}
    d=$run/$name
    mkdir -p "$d/raw" "$d/out"
    cp "$repo/experiments/$src.rs" "$run/context/src/main.rs"
    sha256sum "$run/context/src/main.rs" > "$d/source-sha256.txt"
    start=$(date +%s)
    echo "instrument $name"
    CARGO_TARGET_DIR="$d/instrumented" RUSTFLAGS="-Ctarget-cpu=x86-64-v3 -Cprofile-generate=$run/default" cargo build --manifest-path "$run/context/Cargo.toml" --target x86_64-unknown-linux-gnu --release --offline > "$d/instrument.log" 2>&1
    SD_THREADS=12 SD_DATA="$result/training-sample2" SD_OUT="$d/out" LLVM_PROFILE_FILE="$d/raw/%m-%p.profraw" "$d/instrumented/x86_64-unknown-linux-gnu/release/solution"
    if [ "$name" = baseline ]; then
        cp "$d/out/results.txt" "$run/training-expected.txt"
    else
        cmp "$d/out/results.txt" "$run/training-expected.txt"
    fi
    "$profdata" merge -o "$d/profile.profdata" "$d"/raw/*.profraw
    "$profdata" show --counts "$d/profile.profdata" > "$d/profile-summary.txt"
    awk '/Maximum function count:/ { if ($NF + 0 > 0) ok=1 } END { exit !ok }' "$d/profile-summary.txt"
    echo "optimize $name"
    CARGO_TARGET_DIR="$d/optimized" RUSTFLAGS="-Ctarget-cpu=x86-64-v3 -Cprofile-use=$d/profile.profdata -Cllvm-args=-pgo-warn-missing-function" cargo build --manifest-path "$run/context/Cargo.toml" --target x86_64-unknown-linux-gnu --release --offline > "$d/optimize.log" 2>&1
    cp "$d/optimized/x86_64-unknown-linux-gnu/release/solution" "$run/$name-pgo-x86"
    sha256sum "$run/$name-pgo-x86" > "$d/binary-sha256.txt"
    end=$(date +%s)
    peak=$(cat /sys/fs/cgroup/memory.peak)
    printf '%s\t%s\t%s\t%s\n' "$name" "$start" "$end" "$peak" >> "$run/builds.tsv"
done
grep -Ein 'warning:|profile.*(missing|mismatch)|hash mismatch' "$run"/*/optimize.log > "$run/profile-warnings.txt" || :

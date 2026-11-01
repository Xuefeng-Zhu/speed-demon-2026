#!/bin/sh
# Run inside the pinned Rust x86-64 image, offline, with a 2 GiB container cap.
set -eu
repo=${1:-/work}
result=${2:-/result}
sample=${3:-/result/training-sample2}
full=${4:-/result/training-full2}
run=${5:-$result/opt9-pgo-scale}
source=$repo/experiments/b-opt9/baseline.rs
expected=c5cced6f876b8c89cb7c11874580c81d60554ce1e73ff7dc8426d0d4fe30ce19
[ ! -e "$run" ] || { echo "Refusing existing run directory: $run" >&2; exit 2; }
for data in "$sample" "$full"; do
    test -s "$data/docs.txt"
    test -s "$data/queries.txt"
done
cmp "$repo/track-b/generator.py" "$repo/official/generators/b_index.py"
actual=$(sha256sum "$source" | cut -d ' ' -f 1)
[ "$actual" = "$expected" ] || { echo 'Baseline source hash differs' >&2; exit 2; }
test "$(uname -m)" = x86_64
rustc --version | grep -q '^rustc 1\.99\.1 '
mkdir -p "$run/context/src" "$run/context/.cargo" "$run/logs" "$run/profile-default"
cp "$repo/track-b/Cargo.toml" "$repo/track-b/Cargo.lock" "$run/context/"
cp "$repo/track-b/.cargo/config.toml" "$run/context/.cargo/"
cp "$source" "$run/context/src/main.rs"
{
    rustc -vV
    cargo --version
    uname -a
    echo 'threads=12'
    echo "baseline_sha256=$actual"
    echo 'target=x86_64-unknown-linux-gnu'
    echo 'cpu=x86-64-v3'
    echo "allow_hidden_cpu_flags=${PGO_ALLOW_HIDDEN_CPU_FLAGS:-0}"
    for file in memory.max memory.swap.max memory.peak memory.events; do
        if [ -r "/sys/fs/cgroup/$file" ]; then
            echo "cgroup_begin_$file:"
            cat "/sys/fs/cgroup/$file"
        fi
    done
} > "$run/metadata.txt"
for flag in avx avx2 bmi1 bmi2 f16c fma movbe xsave abm cx16 lahf_lm popcnt ssse3 sse4_1 sse4_2; do
    if ! grep -qw "$flag" /proc/cpuinfo; then
        if [ "${PGO_ALLOW_HIDDEN_CPU_FLAGS:-0}" != 1 ]; then
            echo "CPU flag missing: $flag; stopping before compiling/running v3" >&2
            exit 2
        fi
        echo "Hidden CPU flag accepted for local emulation only: $flag" >> "$run/metadata.txt"
    fi
done
sha256sum "$repo/track-b/generator.py" "$repo/official/generators/b_index.py" > "$run/generator-hashes.txt"
sha256sum "$sample/docs.txt" "$sample/queries.txt" "$full/docs.txt" "$full/queries.txt" > "$run/training-input-hashes.txt"
test "$(wc -l < "$sample/docs.txt")" -eq 25000
test "$(wc -l < "$full/docs.txt")" -eq 250000
test "$(wc -l < "$sample/queries.txt")" -eq 5000
test "$(wc -l < "$full/queries.txt")" -eq 50000
host=$(rustc -vV | sed -n 's/^host: //p')
profdata="$(rustc --print sysroot)/lib/rustlib/$host/bin/llvm-profdata"
test -x "$profdata"
"$profdata" --version >> "$run/metadata.txt"
printf 'phase\tstart_epoch_s\tend_epoch_s\telapsed_s\tstatus\tcgroup_cumulative_peak_bytes\n' > "$run/phases.tsv"
run_phase() {
    label=$1
    shift
    start=$(date +%s)
    echo "PGO phase: $label"
    if "$@" > "$run/logs/$label.log" 2>&1; then status=0; else status=$?; fi
    end=$(date +%s)
    peak=unavailable
    if [ -r /sys/fs/cgroup/memory.peak ]; then peak=$(cat /sys/fs/cgroup/memory.peak); fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$label" "$start" "$end" "$((end-start))" "$status" "$peak" >> "$run/phases.tsv"
    if [ "$status" -ne 0 ]; then
        cat "$run/logs/$label.log" >&2
        exit "$status"
    fi
}
run_phase instrument env CARGO_TARGET_DIR="$run/instrumented" RUSTFLAGS="-Ctarget-cpu=x86-64-v3 -Cprofile-generate=$run/profile-default" cargo build --manifest-path "$run/context/Cargo.toml" --target x86_64-unknown-linux-gnu --release --offline
instrumented=$run/instrumented/x86_64-unknown-linux-gnu/release/solution
sha256sum "$instrumented" > "$run/instrumented-sha256.txt"
for scale in sample full; do
    case $scale in sample) data=$sample;; full) data=$full;; esac
    mkdir "$run/$scale" "$run/$scale/raw" "$run/$scale/training-out"
    run_phase "train-$scale" env SD_THREADS=12 SD_DATA="$data" SD_OUT="$run/$scale/training-out" LLVM_PROFILE_FILE="$run/$scale/raw/%m-%p.profraw" "$instrumented"
    test -s "$run/$scale/training-out/results.txt"
    set -- "$run/$scale/raw"/*.profraw
    test -s "$1"
    run_phase "merge-$scale" "$profdata" merge -o "$run/$scale/merged.profdata" "$@"
    run_phase "summary-$scale" "$profdata" show --counts "$run/$scale/merged.profdata"
    awk '/Maximum function count:/ { if ($NF + 0 > 0) ok=1 } END { exit !ok }' "$run/logs/summary-$scale.log"
    sha256sum "$run/$scale/training-out/results.txt" "$run/$scale/merged.profdata" >> "$run/training-artifact-hashes.txt"
    run_phase "optimize-$scale" env CARGO_TARGET_DIR="$run/$scale/optimized" RUSTFLAGS="-Ctarget-cpu=x86-64-v3 -Cprofile-use=$run/$scale/merged.profdata -Cllvm-args=-pgo-warn-missing-function" cargo build --manifest-path "$run/context/Cargo.toml" --target x86_64-unknown-linux-gnu --release --offline
    cp "$run/$scale/optimized/x86_64-unknown-linux-gnu/release/solution" "$run/$scale-pgo-x86"
done
# Validation is deliberately separate from the prospective per-variant build cost.
for scale in sample full; do
    for check_scale in sample full; do
        case $check_scale in sample) data=$sample;; full) data=$full;; esac
        output=$run/$scale/check-$check_scale
        mkdir "$output"
        run_phase "validate-$scale-on-$check_scale" env SD_THREADS=12 SD_DATA="$data" SD_OUT="$output" "$run/$scale-pgo-x86"
        cmp "$run/$check_scale/training-out/results.txt" "$output/results.txt"
    done
done
sha256sum "$run/sample-pgo-x86" "$run/full-pgo-x86" > "$run/optimized-sha256.txt"
if grep -Ein 'warning:|profile.*(missing|mismatch)|hash mismatch' "$run/logs/optimize-sample.log" "$run/logs/optimize-full.log" > "$run/profile-warnings.txt"; then
    echo 'Inspect profile-warnings.txt before using these binaries.'
fi
for file in memory.max memory.swap.max memory.peak memory.events; do
    if [ -r "/sys/fs/cgroup/$file" ]; then
        echo "cgroup_end_$file:" >> "$run/metadata.txt"
        cat "/sys/fs/cgroup/$file" >> "$run/metadata.txt"
    fi
done
echo "PGO A/B complete: $run/sample-pgo-x86 and $run/full-pgo-x86"

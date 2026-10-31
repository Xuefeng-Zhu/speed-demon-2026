#!/usr/bin/env bash
# Linux x86-64-v3 only. Creates a fresh isolated training directory; never uses /data.
set -euo pipefail
cd "$(dirname "$0")"
if [[ $(uname -m) != x86_64 ]]; then echo 'requires x86_64' >&2; exit 1; fi
if ! rustc --version | grep -Eq '^rustc 1\.99\.1([[:space:]]|$)'; then echo 'requires rustc 1.99.1' >&2; exit 1; fi
for flag in avx avx2 bmi1 bmi2 f16c fma movbe xsave abm cx16 lahf_lm popcnt ssse3 sse4_1 sse4_2; do
  grep -qw "$flag" /proc/cpuinfo || { echo "missing CPU feature: $flag" >&2; exit 1; }
done
host=$(rustc -vV | sed -n 's/^host: //p')
profdata="$(rustc --print sysroot)/lib/rustlib/$host/bin/llvm-profdata"
test -x "$profdata" || { echo 'matching llvm-profdata unavailable' >&2; exit 1; }
work=$(mktemp -d "${TMPDIR:-/tmp}/sd-b-light30.XXXXXXXX")
mkdir "$work/raw" "$work/train-out" "$work/ref-out"
echo "Work directory: $work"
rustc -vV | tee "$work/rust-version.txt"
"$profdata" --version | tee "$work/profdata-version.txt"
python3 generator.py --seed 2 --scale sample --out "$work/training"
flags=(--edition=2021 --target x86_64-unknown-linux-gnu -C opt-level=3 -C lto=fat -C codegen-units=1 -C panic=abort -C target-cpu=x86-64-v3)
rustc "${flags[@]}" "-Cprofile-generate=$work/raw" profile.rs -o "$work/instrumented"
SD_DATA="$work/training" SD_OUT="$work/train-out" LLVM_PROFILE_FILE="$work/raw/%m-%p.profraw" "$work/instrumented" 2> "$work/train-diagnostic.log"
python3 reference.py --data "$work/training" --out "$work/ref-out"
cmp "$work/train-out/results.txt" "$work/ref-out/results.txt"
shopt -s nullglob
profiles=("$work"/raw/*.profraw)
(( ${#profiles[@]} > 0 )) || { echo 'no profile data generated' >&2; exit 1; }
for profile in "${profiles[@]}"; do test -s "$profile"; done
"$profdata" merge -o "$work/merged.profdata" "${profiles[@]}"
"$profdata" show --counts "$work/merged.profdata" > "$work/profile-summary.txt"
awk '/Maximum function count:/ { if ($NF + 0 > 0) ok=1 } END { exit !ok }' "$work/profile-summary.txt"
rustc "${flags[@]}" "-Cprofile-use=$work/merged.profdata" -Cllvm-args=-pgo-warn-missing-function profile.rs -o "$work/diagnostic-pgo" 2>&1 | tee "$work/profile-use-build.log"
echo "Diagnostic binary: $work/diagnostic-pgo"
echo "Inspect rust-version.txt, profdata-version.txt, profile-summary.txt and profile-use-build.log before accepting the diagnostic."

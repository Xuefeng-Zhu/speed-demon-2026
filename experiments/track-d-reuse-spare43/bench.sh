#!/bin/bash
# Usage: bench.sh ROUNDS "THREADS..." VOLUME
# Builds timing probes (make_probe.py) of baseline.rs and ../../track-d/src/main.rs
# with the track's Dockerfile, then runs them alternately in a container with the
# check.py restrictions. VOLUME is a Docker volume holding graph.txt and
# queries.txt (full seed 1). For each thread count, round 0 is an unrecorded
# warm-up; every later run prints one line: variant, threads, round, the probe's
# phase marks, wall time, cgroup peak, THP faults (from /proc/vmstat) and the
# first 12 hex digits of the output's SHA-256.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
rounds=$1; ths=$2; vol=$3
work=$(mktemp -d /tmp/sd-d-reuse.XXXXXX)
for v in baseline candidate; do
  mkdir -p "$work/$v/src"
  cp "$repo/track-d/Cargo.toml" "$repo/track-d/Cargo.lock" "$repo/track-d/Dockerfile" "$work/$v/"
  printf 'target\n' > "$work/$v/.dockerignore"
done
python3 "$here/make_probe.py" "$here/baseline.rs" "$work/baseline/src/main.rs"
python3 "$here/make_probe.py" "$repo/track-d/src/main.rs" "$work/candidate/src/main.rs"
for v in baseline candidate; do docker build -q -t "sd-d-reuse-$v" "$work/$v" > /dev/null; done
mkdir -p "$work/out" && chmod 777 "$work/out"
for th in $ths; do
  for r in $(seq 0 "$rounds"); do
    for v in baseline candidate; do
      out=$(docker run --rm --network=none --read-only --tmpfs /tmp:rw,size=1g --memory=8g --memory-swap=8g \
        --pids-limit=512 --cap-drop=ALL --user 65534:65534 -v "$vol":/data:ro -v "$work/out":/out \
        -e SD_THREADS="$th" --entrypoint sh "sd-d-reuse-$v" -c '
          a=$(grep "^thp_fault_alloc " /proc/vmstat | cut -d" " -f2)
          s=$(date +%s%N); /app/solution 2>&1; e=$(date +%s%N)
          b=$(grep "^thp_fault_alloc " /proc/vmstat | cut -d" " -f2)
          echo "wall_us $(( (e - s) / 1000 )) peak $(cat /sys/fs/cgroup/memory.peak) thp $((b - a))"
          sha256sum /out/distances.txt | cut -c1-12')
      [ "$r" -eq 0 ] || echo "$v th=$th r=$r $(echo "$out" | tr '\n' ' ')"
    done
  done
done
rm -rf "$work"

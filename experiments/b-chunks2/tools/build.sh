#!/bin/sh
# Usage: build.sh <main.rs> <name> [generic]
# Builds <main.rs> in a scratch copy of the track-b crate (same Cargo.toml, Cargo.lock and
# .cargo/config.toml, so the repository's src/main.rs is never swapped) and copies the
# binary to $BIN/<name>. With "generic" it builds for plain x86-64 instead of x86-64-v3.
set -e
SRC=${1:?main.rs}; NAME=${2:?name}; MODE=${3:-native}
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
D=${CH2:-/projects/sandbox/.data/ch2}; BIN=${BIN:-/projects/sandbox/.data/bin}
C=$D/crate; mkdir -p "$C/src" "$C/.cargo" "$BIN"
cp "$REPO/track-b/Cargo.toml" "$REPO/track-b/Cargo.lock" "$C/"
cp "$REPO/track-b/.cargo/config.toml" "$C/.cargo/"
cp "$SRC" "$C/src/main.rs"; touch "$C/src/main.rs"
if [ "$MODE" = generic ]; then
  (cd "$C" && RUSTFLAGS='-Ctarget-cpu=x86-64' cargo build --release --target-dir "$D/tgt-generic" 2>&1 | grep -E 'warning|error|Finished')
  cp "$D/tgt-generic/release/solution" "$BIN/$NAME"
else
  (cd "$C" && RUSTFLAGS='-Ctarget-cpu=x86-64-v3' cargo build --release --target-dir "$D/tgt" 2>&1 | grep -E 'warning|error|Finished')
  cp "$D/tgt/release/solution" "$BIN/$NAME"
fi
sha256sum "$BIN/$NAME"

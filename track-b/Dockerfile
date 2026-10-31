FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS train_data
COPY generator.py /generator.py
RUN python3 /generator.py --seed 2 --scale sample --out /training

FROM halloumee/speed-demon-rust:1.99.1-trixie-llvm-tools@sha256:13e4ee7135d8eac6c56476c7d1aee201f36479f4745fd5d0e6b4529f4e13251a AS build
WORKDIR /src
COPY . .
COPY --from=train_data /training /training
RUN set -eu; \
    test "$(uname -m)" = x86_64; \
    for flag in avx avx2 bmi1 bmi2 f16c fma movbe xsave abm cx16 lahf_lm popcnt ssse3 sse4_1 sse4_2; do grep -qw "$flag" /proc/cpuinfo; done; \
    mkdir -p /pgo/raw /training-out; \
    CARGO_TARGET_DIR=/tmp/instrumented RUSTFLAGS='-Ctarget-cpu=x86-64-v3 -Cprofile-generate=/pgo/raw' cargo build --target x86_64-unknown-linux-gnu --release --offline; \
    SD_DATA=/training SD_OUT=/training-out LLVM_PROFILE_FILE='/pgo/raw/%m-%p.profraw' /tmp/instrumented/x86_64-unknown-linux-gnu/release/solution; \
    test -s /training-out/results.txt; \
    host="$(rustc -vV | sed -n 's/^host: //p')"; \
    profdata="$(rustc --print sysroot)/lib/rustlib/$host/bin/llvm-profdata"; \
    test -x "$profdata"; "$profdata" --version; \
    set -- /pgo/raw/*.profraw; test -s "$1"; \
    "$profdata" merge -o /pgo/merged.profdata "$@"; test -s /pgo/merged.profdata; \
    "$profdata" show --counts /pgo/merged.profdata > /pgo/profile-summary.txt; \
    cat /pgo/profile-summary.txt; \
    awk '/Maximum function count:/ { if ($NF + 0 > 0) ok=1 } END { exit !ok }' /pgo/profile-summary.txt; \
    CARGO_TARGET_DIR=/tmp/optimized RUSTFLAGS='-Ctarget-cpu=x86-64-v3 -Cprofile-use=/pgo/merged.profdata -Cllvm-args=-pgo-warn-missing-function' cargo build --target x86_64-unknown-linux-gnu --release --offline

FROM debian:13-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad
COPY --from=build /tmp/optimized/x86_64-unknown-linux-gnu/release/solution /app/solution
ENTRYPOINT ["/app/solution"]

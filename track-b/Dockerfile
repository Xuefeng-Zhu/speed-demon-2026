FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS train_data
COPY generator.py /generator.py
RUN python3 /generator.py --seed 2 --scale sample --out /training

FROM halloumee/speed-demon-rust:1.99.1-trixie-llvm-tools@sha256:13e4ee7135d8eac6c56476c7d1aee201f36479f4745fd5d0e6b4529f4e13251a AS build
WORKDIR /src
COPY . .
COPY --from=train_data /training /training
RUN CARGO_TARGET_DIR=/tmp/instrumented RUSTFLAGS='-Ctarget-cpu=x86-64-v3 -Cprofile-generate=/pgo/raw' cargo build --target x86_64-unknown-linux-gnu --release --offline
RUN SD_DATA=/training SD_OUT=/training-out LLVM_PROFILE_FILE='/pgo/raw/%m-%p.profraw' /tmp/instrumented/x86_64-unknown-linux-gnu/release/solution
RUN llvm-profdata merge -o /pgo/merged.profdata /pgo/raw
RUN CARGO_TARGET_DIR=/tmp/optimized RUSTFLAGS='-Ctarget-cpu=x86-64-v3 -Cprofile-use=/pgo/merged.profdata' cargo build --target x86_64-unknown-linux-gnu --release --offline

FROM debian:13-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad
COPY --from=build /tmp/optimized/x86_64-unknown-linux-gnu/release/solution /app/solution
ENTRYPOINT ["/app/solution"]

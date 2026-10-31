FROM gcc:15@sha256:eb5e64286ad47187b32bda75c6b6916166ecb41da56559b8b09e0001748d2cce AS build
WORKDIR /build
COPY main.cpp .
RUN g++ -std=c++17 -O3 -march=native -pthread -static -o ingest main.cpp

FROM debian:13-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad
COPY --from=build /build/ingest /app/ingest
ENTRYPOINT ["/app/ingest"]

# Pinned static source count comparison

Measured on ARM Linux Docker using the organizer's pinned `clang-format` 23.1.3 (LLVM style) and `scc` 4.1.0, on temporary copies of the source and corresponding track Dockerfile. This reproduces the relevant formatting and scc flags of `official/harness/static_axes.py`; it is not an end-to-end official board audit. README, PERF and TOML files are excluded by the harness as prose or data. No external runtime dependencies are added by these candidates.

| Track | Candidate | C++ code | Dockerfile code | S total |
|---|---|---:|---:|---:|
| A | selected f45c4cf | 120 | 7 | 127 |
| A | three-shard buffered | 219 | 7 | 226 |
| C | selected f45c4cf | 160 | 7 | 167 |
| C | mmap | 191 | 7 | 198 |
| D | selected f45c4cf | 161 Rust | 8 | 169 |
| D | parallel parser | 192 Rust | 8 | 200 |

For A the experiment needs `-pthread` added to the existing Dockerfile RUN command; that does not change the seven Dockerfile code lines. C uses the selected Dockerfile unchanged. The selected baseline source files were extracted from commit f45c4cf with `git show`, rather than read from a potentially changing working tree. The D Rust files were formatted with `rustfmt 1.10.0-stable` from the allowlisted `rust:1-slim-trixie` image at rustc 1.99.1, using the default config and edition 2021, and counted with the same scc binary. D reproduction details are in the Rust investigator's report.

The upstream-pinned downloads were SHA-256 verified before use: `scc_Linux_arm64.tar.gz` = `6e0d2a1f8d3540ba7df185477dec40bb7340f1b214bfd303147de5cad2bd7b8b`; `clang_format-23.1.3` ARM64 wheel = `072113527b49a9c0ab9058006d9fe20e583823e6482608a34e1883dd2c49ae7d`. C++ source+Dockerfile reproduction, after extracting the `scc` and `clang-format` executables to `/tmp/speed-static-score/bin`, is `python3 /tmp/speed-static-score/reproduce-cpp.py` with access to Docker. The script applies `clang-format --style=LLVM --assume-filename=/work/src/main.cpp`, followed by `scc --no-config --no-gitignore --no-ignore --no-scc-ignore --no-gitmodule --no-cocomo --no-size --no-complexity --by-file --format json /work/src`. Containers use `--network=none --read-only`, and each input is mounted read-only after formatting. JSON output is under `/tmp/speed-static-score/results/`.

Using the supplied dot VM medians and RSS, and assuming equal dependency factors and no memory cap, relative K for A is `sqrt(0.386/0.200) * (25.2/36.0)^0.20 * (127/226)^0.15 = 1.1865`; for C it is `sqrt(0.462/0.415) * (167/198)^0.15 = 1.0285` (same reported RSS); for D it is `sqrt(2.262/2.138) * (169/200)^0.15 = 1.0029` (same reported RSS). These are estimates from shared-VM process metrics, not official board scores; official timing, cgroup memory and unseen data may differ.

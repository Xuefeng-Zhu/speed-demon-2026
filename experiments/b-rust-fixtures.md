# Running legacy B fixtures against Rust

Build the selected Track B once, offline, then use the positional adapter for
fixtures that expect a C++ executable accepting `DOCS QUERIES RESULTS`:

```sh
(cd track-b && cargo build --release --offline)
export B_RUST_BINARY="$PWD/track-b/target/release/solution"
python3 experiments/b-bounded-boundary.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-fuzz.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-shards.py "$PWD/experiments/b-rust-positional-adapter.py"
python3 experiments/b-bounded-duplicates.py "$PWD/experiments/b-rust-positional-adapter.py"
```

The adapter makes temporary links named `docs.txt` and `queries.txt`, sets
`SD_DATA` and `SD_OUT` for the Rust binary, and copies its `results.txt` to
the path requested by the fixture. It does not modify either input file. The
fixture's timing and process RSS can include adapter overhead and must not be
used as benchmark evidence. The direct equivalent for the boundary fixture is
`python3 experiments/b-stream-boundary.py --binary "$B_RUST_BINARY"`; omit
`--binary` to build the selected track in a temporary target directory.

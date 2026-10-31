# Track B: Index

This standard-library Rust implementation reads queries first, partitions the corpus into contiguous line-aligned chunks and answers queries per chunk. Identical phrases share bounded count, sum and first-ten summaries. Boolean expressions retain strict left-to-right semantics; bitmap payload is globally capped and sorted postings provide an exact fallback. Chunk summaries are merged in document order. The program reads `/data/docs.txt` and `/data/queries.txt`, and writes `/out/results.txt`; `SD_DATA` and `SD_OUT` are local-test overrides.

See `PERF.md` for measurements and correctness evidence. The previous selected C++ source is preserved in `experiments/pr1-c634/baseline-track-b/main.cpp`.

# Nine-worker Track B shard review

Candidate `experiments/b-length-aware/length-9.cpp` SHA-256 `3667c8f167a95137ff535ddcded3ae8e383b2a655f8d58373e4f1b6ab70d9967` changes the selected index to nine workers and uses length-aware token hashing. The shard review checks that contiguous document partitions concatenate in ID order and phrase summaries retain exactly the first ten IDs across worker boundaries. Empty worker partitions, repeated and overlapping phrase occurrences, Boolean operations, Unicode separators, 32-byte tokens, and zero-prefixed terms are included.

On macOS ARM, a Clang C++17 `-O2 -g -pthread -fsanitize=address,undefined` build passed all 49 document-count fixtures against `official/reference/b_index.py`: N=0 through 30, plus 35–37, 63–65, 80–82, 89–91, 99–101, and 179–181. Existing `experiments/b-bounded-shards.py` and `experiments/b-bounded-boundary.py` also passed the same build, including duplicate queries, distributed top-ten, overlap and >1 MiB reads. Clang emitted two pre-existing warnings about unqualified `std::move`; sanitizer diagnostics were absent. These are correctness checks, not target x86 performance or official scoring.

From the repository root, compile a sanitizer binary and run:

```sh
c++ -std=c++17 -O2 -g -pthread -fsanitize=address,undefined experiments/b-length-aware/length-9.cpp -o /tmp/sd-b9-asan
python3 experiments/b-nine-review/shard_reference.py /tmp/sd-b9-asan
python3 experiments/b-bounded-shards.py /tmp/sd-b9-asan
python3 experiments/b-bounded-boundary.py /tmp/sd-b9-asan
```

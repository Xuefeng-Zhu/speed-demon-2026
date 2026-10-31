# Nonlinear packed dictionary: maximum-vocabulary review

This synthetic grammar-valid fixture tests 338,000 distinct query terms of 9–32 bytes: 31,000 six-term Boolean queries and 19,000 eight-term phrases, the maximum distinct-term count at the published full query counts. It uses 600 documents, Unicode separators, repeated phrases, uppercase documents and a mixture of present and absent terms. It intentionally differs from the generated distribution and is a correctness test, not a scoring benchmark.

The test generates inputs in a temporary directory, runs the official Python reference, and requires every supplied candidate output to be byte-identical. From the repository root, for binaries compiled from the nonlinear candidate with optimized and sanitizer settings:

```sh
python3 experiments/b-packed-nonlinear-review/max_vocabulary.py /path/to/optimized /path/to/asan-ubsan
```

The independent review compiled `/tmp/b-packed-nonlinear.cpp` (SHA-256 `a47bc7aac61f03cea55337567ed1e7991aff067eddba3ddf4d3c0877a201ba2a`) with `clang++ -std=c++17 -O3 -DNDEBUG -pthread` and separately with `clang++ -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -pthread`. Both matched the official reference, SHA-256 `6800256763e95e978ef7e501a052eed5f11b50b370781bd47bc52098d7b55ed6`, without sanitizer diagnostics. The two compiler warnings were about unqualified `std::move` calls; neither identified a runtime defect.

The packed keys are zero-initialized, cover all 32 token bytes and compare all key bytes after a hash hit. A prefix cannot match a longer valid alphanumeric token because its following zero byte differs. The table's power-of-two capacity is at least twice the number of query terms. Dictionary contents are immutable while workers look up terms. Phrase grouping and bounded per-worker count/sum/top-ten summaries are unchanged from the previous selected implementation. The nonlinear hash removes the particular easy collision family previously demonstrated for the linear candidate; it is not a proof against adversarial hash-flooding in general.

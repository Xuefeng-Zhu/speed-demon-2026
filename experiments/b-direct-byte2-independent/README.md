# Independent direct-byte2 lookup tests

This reviews the isolated candidate `../b-direct-byte2-current/candidate.rs`, SHA-256 `a2691fb564324be0fd4427adad67561d6374be6a27a3d83674343fd29eaaa727`, against current selected baseline SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`. It is not selected source.

The candidate stores IDs for 1–2-byte normalized ASCII alphanumeric tokens in an exact 65,536-entry table, using the two normalized bytes as an injective index; zero-padding of a one-byte token cannot equal a valid two-byte token. `build_short` initializes the table before sample and full corpus scans. The new lookup indexes the second input byte only for a valid two-byte token; longer tokens keep the previous hash-table path. Review found no concrete mapping, empty dictionary, sentinel, bounds, or ownership defect under the official token grammar. This is not a proof of all inputs or a performance claim.

`python3 experiments/b-direct-byte2-independent/run.py` verifies the exact source SHA, appends the independent test module to a temporary copy, then compiles and runs normal and test-only forced-short-hash-collision variants with optimization, overflow checks and debug assertions. Both builds passed on native macOS ARM:

* All 36 one-byte and 1,296 two-byte normalized terms, their ASCII upper/lower-case variants, present and partially absent dictionaries, exact-length slices and 65 offsets.
* An empty dictionary and token length 0, and unchanged fallback paths at lengths 3, 8, 9 and 32.
* Real anonymous three-page mappings with inaccessible guard pages on both sides; lookups at the beginning and end of the mapped page for lengths 1, 2, 3, 8 and 9.

The page tests used the native system page size and native scalar environment. They do not exercise the Linux x86 AVX2 classifier, target performance or parent-cgroup memory. No generated data, credentials or executables are included; no Mac Docker was used.

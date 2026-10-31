# Track B query-role histogram

An isolated diagnostic of the selected Rust Track B implementation; this is
instrumentation, not a candidate or a timing benchmark. `baseline.rs` is the
exact selected source (SHA-256
`7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`).
`profile.rs` (SHA-256
`bcb0f642650d67d47689686661b17be3161948e838b505bfb7177af57398131a`)
adds role counters to that source; `profile.log` is its recorded stderr.

On the official public full seed-1 corpus, the eight data intervals covered
253,827,587 bytes, 250,000 documents, and 36,276,657 tokens. The run's output
hash was `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`,
matching the official expected hash. Each token receives one mutually
exclusive category according to the interned query vocabulary and the chosen
phrase anchors after sampling:

| Category | Tokens | Share | Documents containing category |
| --- | ---: | ---: | ---: |
| Boolean term only | 26,794,584 | 73.862% | 249,295 |
| Phrase anchor only | 630,500 | 1.738% | 189,225 |
| Both Boolean term and phrase anchor | 766,634 | 2.113% | 198,584 |
| Phrase non-anchor only | 524,979 | 1.447% | 178,372 |
| Not in the query vocabulary | 7,559,960 | 20.840% | 244,287 |

The vocabulary role counts `[nonanchor-only, bool-only, anchor-only, both]`
were `[8838, 49308, 13465, 4136]`, including short-token counts
`[5647, 32288, 8713, 2754]`. The current hash tables have 524,288 general
slots and 131,072 short slots. Removing nonanchor-only terms would reduce short
keys from 49,402 to 43,755 but would leave the short table at 131,072 slots.
Every corpus token would still need lookup to identify Boolean or anchor roles.
Thus these counts alone do not support a substantial speed gain from omitting
nonanchor-only terms. Hidden workloads may have different distributions.

To reproduce on the same input and worker count (paths are examples):

```sh
rustc --edition=2021 -O -C lto=fat -C codegen-units=1 -C panic=abort experiments/b-role-hit-profile16/profile.rs -o /tmp/b-role-profile
mkdir -p /tmp/b-role-output
SD_DATA=/path/to/full-b SD_OUT=/tmp/b-role-output /tmp/b-role-profile 2>/tmp/b-role.log
shasum -a 256 /tmp/b-role-output/results.txt
python3 experiments/b-role-hit-profile16/summarize.py /tmp/b-role.log
```

`summarize.py` asserts the recorded seed and worker partition. It excludes the
separate sample interval `[0, 524645)` and requires eight contiguous full-data
intervals; adapt sample identification for other inputs or worker counts. The
instrumentation counts tokens and document category presence, not time or
causal savings. The corpus, executable, and output are not included here.

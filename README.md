# Speed Demon 2026 — local candidates

Four independently written solutions for the event's four tracks, prepared during the permitted coding window. The official challenge repository used for specifications, generators, references and checks is `official` at commit `ad1f06063a76bf94066f169e133ec0c2e1485b65`. See `RULES.md` for the rules audit. The starter's MIT license and check script are retained here. No entry has been submitted.

## Verification on October 31, 2026

All four pinned Dockerfiles passed the official Dockerfile allowlist checker. The starter's `check.py` built them offline and ran the seed-1 full datasets with no network, read-only root and data, uid 65534, the specified memory, process and tmpfs limits, and exactly one output file. Each output matched the published SHA-256:

| Track | Full output SHA-256 | Local container wall time |
|---|---|---:|
| A | `495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3` | 0.70 s |
| B | `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927` | 2.32 s |
| C | `d8088b1cd42ba1338b1345b107b55db7b96ef1f5066f3ff64fd26a8912a0f536` | 0.84 s |
| D | `a23dbdf0a3e49cc8901310a9ee1dc6a9a569a85297b6da75c2a7002cb2ed277e` | 1.90 s |

Times include container startup, used an ARM Linux VM on a Mac with some runs concurrent, and are not competition scores or comparisons against the x86 scoring machine. Extra checks: A seed 999 sample against the reference and independent synthetic cases; B seed 99 tiny and randomized corpus/queries against the reference; C seed 42 sample and seeds 2, 3, 12345 tiny against the reference; D seed 7 sample against the reference and 4,500 randomized graph queries against independent Dijkstra. Track READMEs and PERF files contain further details. No local test proves correctness on the private holdout. An additional run of the upstream generator/reference unit suite was interrupted during its Track B edge-case scan after 21 tests had passed; the suite was not completed and does not directly exercise these candidates.

To repeat, generate inputs using `official/generators/<track>.py` and run, for example:

```sh
python3 check.py a --data /absolute/path/to/a-full --expected 495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3
```

Use the corresponding hash from the table for each full seed-1 dataset. The full datasets and local container outputs are generated artifacts, not included in this candidate directory. An earlier version of each track also built for x86-64 and matched published sample hashes under emulation, using temporary Dockerfiles pinned to the official images' amd64 child manifests. The current A–C candidates subsequently matched the published full-data hashes in a native x86 dot VM, including the promoted parallel Track C; see `experiments/dot-vm.md`. A later native x86 Track D run, after Rust was installed, also matched the published full-data hash. The submission Dockerfiles still use the required allowlisted index digests. See `experiments/x86.md` for commands and limits; the x86 checks were not an official timed harness run.

Paired local baseline comparisons and reproducible correctness tests are recorded in `experiments/README.md`; the native x86 results are in `experiments/dot-vm.md`. They support the current optimization choices but do not establish performance on the scoring machine.

## Before entering

- Team name is set to `PeppaPig` in all four track manifests; registration is being handled separately.
- Test on the official board to establish real run IDs, times, memory and scoring; document those runs and actual iterations in `PERF.md`. The board requires a GitHub App and a repository.
- Follow the official event registration/submission and publication rules by the deadline, November 2 at 15:00 UTC. The board app is installed with read-only code and metadata access on the selected private repository; GitHub also includes public repositories read-only. No team registration form or formal submission has been sent.

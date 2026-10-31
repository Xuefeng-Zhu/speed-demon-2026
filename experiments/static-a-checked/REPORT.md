# A checked merge source-score comparison

Selected source at local commit `51d3bd9162665cb7982512c44c97e7ab9bed588b`: C++ 219 plus Dockerfile 7 = S 226. Checked source in the same commit: C++ 226 plus Dockerfile 7 = S 233. Both were extracted with `git show` and counted after LLVM formatting with the organizer-pinned clang-format 23.1.3 and scc 4.1.0, using isolated offline Docker and the official flags; `selected.json` and `checked.json` contain raw counts. This is not a full board static audit.

The dot VM supplied median wall times of 0.2161 s selected and 0.2124 s checked, with peak process RSS 35.84 and 36.07 MiB, respectively. The estimated ratio, assuming equal dependency factors and no memory cap, is `sqrt(0.2161 / 0.2124) * (35.84 / 36.07)^0.20 * (226 / 233)^0.15 = 1.002784`. The ~0.28% estimated gain is below likely shared-VM noise and is not an official score or cgroup result.

Raw source SHA-256: selected `06b51990aead6d6c8cf8549d23cf622baba378bb7bc88d1de42df3d817aad889`; checked `8ca6fd84b940409793a452f35395b4883565ed8134c6b9da4732e027d770bc26`. Reproduction: `/tmp/speed-static-score/compare-a-checked.py`, after placing the hash-verified pinned binaries in `/tmp/speed-static-score/bin` and making the Docker image `speeddemon-check/track-a:latest` available.

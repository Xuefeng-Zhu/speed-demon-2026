# B eight-key AVX2 lookup (unselected)

Baseline SHA-256 `7d371fe84ce9f0fd9d3c7e6fdf02b6b37e0f1440319c654161b990cf27bb8bf3`; candidate `52066aa6f4cb6edfe3ba15f007e251c8729ad9a60349a6290c8c7e18064b756b`. The existing sample selects up to eight short query terms; AVX2 compares the exact normalized key against both four-key groups before falling back to the original dictionary. Sample choice affects only speed. Phrase summaries and bitmap limits are unchanged. This differs from prior slower scalar hot-key trials and the pending packed PEXT candidate.

Independent static review found no concrete AVX equality or bounds defect; its n=0 padding caveat was fixed with an explicit guard. Test-only scalar emulation passed hot-list sizes 0/1/8, n=0, uppercase, digits, 20,000 random lookups, 40 mixed reference corpora, shard/duplicate and >1 MiB boundary cases. The full public seed output matched `f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927`. Eight selected terms accounted for 12,096 of 59,604 matched tokens in the 512 KiB public sample; this diagnostic is not a speed measurement.

Actual x86 AVX2 execution, protected pages, PGO interaction, performance and official cgroup memory are untested. Two vector comparisons per short token may cost more than the saved hash lookup, so do not promote without serialized x86 testing and target practice. Earlier unrelated timing contamination does not affect these correctness checks. No Docker was run on the Mac.

A secret-free archive with baseline, candidate, verification scripts and x86 reproduction commands is in Library as `libfile_8f236ddc9f1c8191bdbe26663b6439af`. Independently downloaded archive SHA-256 `444c51d7886c98ed381d42a3931fb852497a35bed7b8c8ec73f9aa5fd047c15a` matches the local archive.

Parent-run x86 dot VM paired full-seed tests were near tied in the first batch and 6% slower in the second, with higher CPU. Across D coarse, C prefetch and B hot-key, 216 full hashes and alternate/oracle/zero-cycle/fallback/actual SIMD guard checks passed. This native result is not official cgroup scoring; keep the existing selected B.

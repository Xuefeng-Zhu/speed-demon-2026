# C prehashed bucket with inline group bits (not selected)

This alternative builds on `c-hash-bucket` but keeps four group-bit words inline with each borrowed name and next pointer; for more than 256 groups it uses a separate dynamically sized bitmap. The same exact collision-chain promotion is retained. Baseline is selected parser SHA-256 `f71a22c0642250010d967cfb493fbfb95bab01f1c3e4dedac0b93fb2987e80ef`. No alternate-data, forced-collision or independent review was performed; do not promote.

Eleven randomized full-seed ARM pairs plus warmups matched 24 full hashes. Candidate/baseline median wall was 0.11101/0.10852 s and CPU 0.67141/0.66597 s; RSS roughly 228 MB versus 226 MB. These figures do not show a speedup and are not official or x86 measurements. See `arm-report.json`; no Mac Docker was run.

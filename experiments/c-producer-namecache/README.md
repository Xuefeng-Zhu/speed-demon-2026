# Producer name-hash memo — unselected

Baseline is selected salted-owner `0aa4cbccf08b05a59aadbe7eaf23a931e468a95f76463a95100a142e8221bc08`, candidate is `40a59b5f3124cc059bf8ca79d6cd7d65e8391cd8f5c9df25a389061e0308be9f`. Each packed-input parser allocates a direct-mapped 32,768-entry name-hash memo keyed by the first eight encoded bytes and name length, verifying exact bytes against the immutable input map before accepting a hit; a miss computes the baseline Fx hash. Each parser allocates approximately 768 KiB. The fallback remains unchanged.

It passed 120 mixed reference cases. One shared ARM 15-pair full-seed batch produced candidate/baseline median wall 0.09000/0.08748 s and CPU 0.52860/0.50265 s; all 32 full hashes matched. Raw samples are in `arm-report.json`. The candidate shows no speed win in this screen; no full adversarial, protected-page, independent review, Linux x86 or official validation was attempted, and it remains unselected.

# C compact-owner unrotated prehash — unselected

This earlier variant carries a 64-bit Fx prehash in a 16-byte event and uses an unseeded identity hash map keyed by exact name and prehash. It is closely related to `c-owner-rotated`; see that directory for the important adversarial clustering caveat. It has not been independently reviewed or target tested, and the exact selected source is unchanged.

The candidate passed 120 mixed references, 20 long/sentinel/forced-fallback tests, 20 group boundaries, 12 collision/growth tests and 357 CRLF cut comparisons. One 15-pair shared ARM full-data screen matched every hash: candidate/baseline median 0.09700/0.10497 s wall and 0.44774/0.51562 s CPU, with RSS approximately 284/253 MB. The baseline here is the 8-byte compact-owner prototype, not selected; these are not official or x86 measurements. No Mac Docker was run.

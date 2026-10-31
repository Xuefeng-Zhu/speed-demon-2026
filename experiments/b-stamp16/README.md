# B 16-bit document stamps (not selected)

This candidate halves the per-worker Boolean dedup stamp array from 32 to 16 bits. Stamps use 1..65535, clearing to zero after each 65535 documents before reuse; this preserves membership across wraps. All other logic, exact phrase matching and memory caps are unchanged. Nine randomized full-seed shared-macOS ARM pairs after warmup matched the full hash: candidate versus exact baseline median wall 0.602598 vs 0.482507 s and CPU 1.653681 vs 1.641987 s. Contention was significant; no target win is established and the candidate is not selected. Samples in `report.json`.

A temporary forced-one-worker build passed the official full-seed hash over 250,000 documents (three stamp clears), 40 independent mixed-reference corpora, distributed top-ten/phrase overlap checks, and a 250,000-document/19,000 duplicate-phrase stress fixture. This does not execute x86 AVX2. No Docker was used.

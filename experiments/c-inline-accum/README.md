# Track C inline aggregate updates — unselected

The baseline is selected owner SHA-256 `0aa4cbccf08b05a59aadbe7eaf23a931e468a95f76463a95100a142e8221bc08`; candidate `9a48310edb79e503c68102026c56af152ac35b75b486b7cc4d23832ab1dc7f33` explicitly updates seven aggregate fields inside the packed parser. The distinct field remains unchanged, as it did when adding zero in the prior generic merge. The fallback and final merge are unchanged.

It passed 24 mixed reference corpora at five worker counts. One 15-pair shared ARM full-seed run with warmup produced median candidate/baseline wall 0.08853/0.08712 s and CPU 0.50895/0.50764 s, with all 32 output hashes correct. Raw samples are in `arm-report.json`. No target speed improvement is established, no x86 run or independent review was performed, and the candidate remains unselected.

# B stream reserve (not selected)

Candidates change only the initial capacity hint of the per-worker Boolean term stream; Vec growth remains exact and unrestricted. On one instrumented shared-ARM full-seed run with eight workers, each ~31.7 MB chunk emitted ~2.66–2.67 million IDs, growing the original /16 initial capacity once to ~3.97 million slots. Samples depend on the corpus and worker count; capacity never changes semantics.

Nine warmed randomized shared-ARM pairs for /10 versus /16 had candidate wall 0.527530 vs 0.520115 s and CPU 1.669789 vs 1.630084 s. For /8 the first nine-pair batch was 0.304880 vs 0.310041 s and CPU 1.593021 vs 1.601329 s; a 15-pair repeat was 0.381599 vs 0.355320 s and CPU 1.610191 vs 1.632780 s. Every full output hash passed. This is inconclusive native ARM evidence under shared load, not an official or x86 score, and no variant is selected. `/12` is included but has not been timed. No Mac Docker was used.

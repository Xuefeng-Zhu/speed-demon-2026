# B trailing-AND empty shortcut (not selected)

The candidate scans a Boolean query backward until its last OR or first term. If an AND in that suffix has an empty posting, the result is definitely empty because the later AND/NOT operations cannot add documents. This is distinct from the prior forward known-empty state machine. The exact baseline SHA is `322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`; candidate SHA is `87ccb3c55061377596996a2dc88caa006ceac620cfbf2fe58f2f085b937c2330`.

Shared native ARM randomized warmed 11-pair candidate/baseline medians were 0.448168/0.453340 s wall and 1.616578/1.647640 s CPU; 15-pair repeat 0.302065/0.305423 s wall and 1.593215/1.600953 s CPU. All 56 full hashes including warmups passed. Results are noisy scalar-fallback observations, not x86 or official cgroup measurements; no major speedup is established and the candidate is not selected. A diagnostic run skipped approximately 1,756–1,844 of 50,000 queries per worker on seed 1.

The candidate also passed 40 mixed reference corpora, 5,364 Boolean expressions against all 64 membership assignments, and 250,000-document/19,000-duplicate-phrase stress. Target AVX2, independent multi-cap and edge tests remain unverified. No Mac Docker was used.

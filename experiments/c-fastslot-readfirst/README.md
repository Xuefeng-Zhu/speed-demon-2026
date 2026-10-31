# C fast-slot read-before-atomic (not selected)

This isolated candidate derives from `experiments/c-fastslot/candidate.rs`, which is itself experimental and not the selected source. It checks the group bit with a relaxed atomic load before issuing `fetch_or`, avoiding atomic writes when the bit is already known set. Bits only transition zero to one; an observed one is sufficient to skip, while a zero still takes the original atomic operation. No other code is changed. It has not received independent concurrency review, collision tests or x86 testing and must not be promoted from this screening alone.

Eleven paired full-seed native ARM runs following warmup matched every published hash. Median candidate/baseline wall was 0.14428/0.13756 s, CPU 0.77872/0.76716 s. This shared-host screen is noisy and does not indicate a speed gain; individual measurements are in `arm-report.json`. No Mac Docker was used.

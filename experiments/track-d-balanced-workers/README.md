# Balanced D worker count screen (not selected)

These variants differ from selected balanced-frontier D only by forcing 8, 12, 16 or 24 workers for graph construction and querying. They are experimental and no fixed worker count is selected from this screen. Source is input-derived and unchanged in semantics.

Each variant matched the published full seed-1 SHA-256 in one warmup and five randomized measured native ARM Mac runs. Median wall times were 0.259432, 0.259756, 0.263029 and 0.265740 seconds respectively; median CPU was 1.817168, 1.797631, 1.822721 and 1.858054 seconds. Maximum process RSS was 534,593,536, 646,922,240, 775,733,248 and 1,006,518,272 bytes respectively. Individual observations are in `report.json`. They are close, the host was shared, and Mac ARM/process RSS is not target x86 or official cgroup memory. No conclusion is drawn about the scoring box's worker optimum.

For a controlled retest compile each source using the same release/ISA flags, generate the input separately, alternate randomized execution without competing workloads and verify the published output hash each run. No Docker was used.

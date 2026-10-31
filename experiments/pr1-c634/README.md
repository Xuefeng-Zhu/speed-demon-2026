# PR #1 reference source

`track-b.rs` is the unchanged Track B source from PR head `c634a2ad071f3c9ac6f12559c153b1beea98554f`. Its per-query phrase occurrence vectors and dense bitmap cache are not bounded under duplicate-heavy or dense valid inputs, and its linear hash admits a constructed collision family. It is preserved outside the submitted track while bounded adaptations are tested. It is not the selected Track B implementation.

`trimmed-a-hardened.rs` and `trimmed-d-meeting.rs` are tested adaptations of the PR's line reductions. On the shared x86 dot VM, paired medians were 0.05938 versus 0.05436 seconds for trimmed versus existing A, and 1.196 versus 1.1255 seconds for trimmed versus existing D. The speed-first merge retains the prior A and D sources; these native VM figures are not official scores. All four tracks in the original candidate merge passed 12 full official hashes, 12 alternate references and Dockerfile static checks on the VM.

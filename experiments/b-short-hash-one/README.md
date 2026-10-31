# B short-token hash simplifications (not selected)

These isolated candidates reduce the two-multiply short-token hash to a
one-multiply mixing sequence. Exact key comparisons and all other logic remain
unchanged. Baseline source SHA-256 is
`322cc95ee08cf6d4abc5e1b52240753f66c7eaf89ab669cb6d72b0a8487dc458`;
`one.rs` is `4a081142e8cabb5fe09d1b8fc50695224274ac1ffc3b50848ecbd212dc020fff`,
and `simple.rs` is `e53b094d34fe18b45f734187522eb3aad03eb0a6c21d583d5ce3300c25e9c9f7`.

Every full seed-1 output hash matched in randomized native ARM pairs after
warmup. Nine-pair medians were 0.283553 s `one` versus 0.293577 s baseline,
and 0.273786 s `simple` versus 0.274964 s baseline. A 15-pair repeat for `one`
was 0.474770 s versus 0.480931 s baseline. CPU medians were 1.555181 versus
1.578058, 1.538488 versus 1.581408, and 1.590747 versus 1.615671 s
respectively. The shared host was noisy; scalar ARM is not x86 AVX2, and
native process RSS is not cgroup memory. No change is selected from this small
screen; it has not had alternate-reference or forced-collision tests.

`probe-screen.py` inserts all 47,988 one-to-three-byte alphanumeric words into
a 131,072-slot table. Old/one/simple produced 14,020/13,542/18,071 total extra
probes and 16/12/19 maximum extra probes in that order. This is only a fixed
nonadversarial screen, **not** proof against collision flooding; changing the
hash would require adversarial distribution and exact-collision validation as
well as controlled x86 timing. `*-screen.json` and `one-repeat.json` retain
all samples. No Docker was used.

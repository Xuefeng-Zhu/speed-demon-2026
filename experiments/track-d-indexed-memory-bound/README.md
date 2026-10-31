# D indexed-radix memory accounting (conditional, not a cgroup proof)

This is an independent allocation analysis of the experimental `track-d-indexed-radix/candidate.rs`, not an endorsement of the candidate's correctness or performance. Full official dimensions are `n=1,740,512`, `m=5,000,000`, 2,000 queries, 12 worker threads. All sizes below are bytes on 64-bit systems; MiB means 2^20 bytes. The experimental source caps its worker count at 12.

## Search state

Each of the 12 workers can retain both searches after a wide fallback. For each vertex, the searches reserve:

- `dist`: 8 bytes narrow plus 16 bytes wide = 24n;
- narrow and wide `touched` vectors: 4 bytes each, preallocated to n = 8n;
- four indexed radix heaps: two directions times two searches, each `links` entry two u32 = 32n.

Total fixed payload is `64*n*12 = 1,336,713,216` bytes (1,274.79 MiB). Each heap has another 65 bucket-head u32 values and bookkeeping. The touched condition inserts each vertex at most once per query, so its n-element preallocation does not grow for valid inputs; each links array also has exactly n logically addressable entries. Rust allocation APIs provide at least the requested capacity, not a portable contractual maximum on actual allocator footprint. Actual charged pages depend on how many pages are touched.

## Loader and data, conditional envelope

A graph edge line is at most `7+1+7+1+10+1 = 27` bytes, and the header is at most 16 bytes, giving a graph file bound of `27*m+16 = 135,000,016` bytes. Sum of the 12 positioned-read buffers is at most this length plus `12*33` bytes. For a conservative cgroup scenario, count file cache and read buffers separately, `270,000,428` bytes, although accounting and residency can differ.

For 12 loader workers, the code constructs 2 directions × 12 workers × 12 blocks = 288 edge vectors. The initial capacity per vector is `c = floor(floor(m/12)/12)*9/8 + 64 = 39,126` entries. There are exactly `2*m` inserted `(u32,u32,u32)` edge tuples, 12 bytes each. **If** the actual `Vec`/allocator growth is geometric doubling, never delivers excess capacity beyond the requested capacity, and reallocations use at most old and new payloads, final capacity per bucket is bounded by `c + 2*len`. Summing across vectors yields `(288*c + 4*m)*12 = 375,219,456` bytes. A deliberately conservative sum of all old and new bucket payload allocations, including unreused freed pages through geometric growth, is less than twice that: `750,438,912` bytes. The standard `Vec` contract does not guarantee these allocator details; a formal implementation bound requires a controlled allocator or fixed memory regions.

The two packed CSR payloads total `2*(4*(n+1) + 8*m) = 93,924,104` bytes. Both passes' full cursor slices together total at most `8*n = 13,924,096` bytes if conservatively counted together. These figures count both compact and wide arrays; they do not assume untouched wide pages are free.

## Illustrative sum and missing terms

Add the search payload, deliberately cumulative loader-vector payload, both CSR graphs and cursors, input buffers and one full graph file cache, 4 phases × 12 threads × 2 MiB stack allowance, and an 8 MiB main stack allowance. The result is `2,574,052,660` bytes (2.397 GiB), leaving 5.603 GiB below 8 GiB **before** allocator overhead, heap fragmentation, thread/TLS metadata, process libraries, query/output buffers, cgroup-charged kernel memory, other harness or process allocations, and potential additional cached files. Four sets of stacks are included conservatively in case freed mappings remain charged; stack size and caching must be verified or explicitly configured. The graph and query bounds assume the official input grammar and dimensions, not a claimed graph distribution.

This arithmetic is useful design headroom, **not a proof of a less-than-8-GiB parent-cgroup peak**. The competition material does not specify a portable upper bound on `Vec` over-allocation, global allocator behavior, retained/free page accounting, kernel charges, helper processes or other cgroup-charged cache. A formal bound requires fixing those mechanisms or proving an enforceable runtime budget that includes them, and an audit of the actual scoring harness. Synthetic cgroup peak tests are evidence, not a universal proof. The indexed queue's correctness, fallback behavior, runtime cost, and page-cache/allocator behavior also require independent validation on the target.

## Capped-hybrid requested-payload comparison

For the isolated capped-hybrid candidate SHA-256 `671c639be3400209e83e080dfb54947affd30ca71dc34ec17804d24d70292d9c`, the narrow search requests `8*n` bytes of distance pairs, `4*n` touched indices, and two fixed pools of `65,536 * 16` bytes per worker. If all 12 workers also retain wide fallback state, that requests `16*n` wide distance bytes, `4*n` wide touched bytes, and `16*n` indexed links per worker. Totals are:

| Component | 12-worker requested bytes |
| --- | ---: |
| Narrow distances | 167,089,152 |
| Narrow touched | 83,544,576 |
| Two fixed narrow pools per worker | 25,165,824 |
| Wide distances | 334,178,304 |
| Wide touched | 83,544,576 |
| Wide indexed links | 334,178,304 |
| **Search payload total** | **1,027,700,736** |

Substituting this total into the same conditional illustrative envelope above gives **2,265,040,180 bytes** (2.109 GiB), leaving 5.891 GiB nominal headroom below 8 GiB before the previously listed unspecified charges. The two pool arrays each retain their capacity but do not grow past their fixed logical cap; exhausting one triggers a wide rerun. Rust's allocation footprint, loader growth assumptions and the remaining parent-cgroup charges still prevent claiming a formal 8 GiB bound from this arithmetic. This is not a correctness, target performance or cgroup stress result.

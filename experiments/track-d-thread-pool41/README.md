# D persistent worker threads (rejected)

`baseline.rs` is `track-d/src/main.rs` at `7b43b63`. Each `parallel` call spawns and joins one scoped thread per CPU, about 8 calls per run plus the forward CSR build's own scope.

- `spawn.rs` adds three rounds of eight empty `parallel` calls before the real work. On the 8-thread sandbox, a round took 1.26–1.66 ms, about 0.2 ms per call.
- `pool.rs` replaces `parallel` with a persistent pool: one worker per CPU, each fed boxed jobs over a channel, with the job lifetime extended because `parallel` waits for every result before returning.

Its output matched the full seed-1 SHA-256. Over 31 alternating sandbox runs, the baseline measured 169.5 ms median (min 164.0) and the pool 171.0 ms (min 161.4). The pool was 0.9% slower on the median and 1.6% faster on the minimum, so there is no measurable gain.

The pool adds 22 formatted code lines (379 → 401) and an `unsafe` lifetime extension. With no time gain, the extra lines cost about 0.8% K (`(379/401)^0.15`). Not selected.

# Track B: Index

Prototype for the [Track B specification](https://github.com/hackathon-raptors/speed-demon-2026/blob/main/specs/b-index.md). Set the actual team name before registering or submitting.

The program reads queries first and assigns IDs to query terms. It tokenizes each document once, recording a sorted document posting list for every relevant term and a sequence of token IDs for phrase evaluation. Boolean operations use ordered set operations, preserving left-to-right semantics. Phrase queries scan documents in the shortest posting list for consecutive tokens. Finally it writes count, sum, and up to ten lowest matching IDs.

No external runtime dependencies. Compilation requires C++17. In the container, input is read from `/data` and output written to `/out/results.txt`.

Further work: profile full scale on the competition hardware, investigate parallel indexing, and measure the impact of reducing phrase scans and sorting costs. Do not infer competition scores from local native timings.

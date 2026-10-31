#!/usr/bin/env python3
"""Deterministic randomized search for an improvement below the narrow cutoff."""
import hashlib
import pathlib
import subprocess
import tempfile

here = pathlib.Path(__file__).resolve().parent
source = (here.parent / "track-d-coarse-forward-prune29" / "candidate.rs").read_text()
assert hashlib.sha256(source.encode()).hexdigest() == "c33d3984871fb22ed7c2d678b3a3562ac82d46cb952a8a0461980301c5a553ef"
needle = "if other != 0 { best = best.min(nd + (!other) as u64); }"
replacement = """if other != 0 {
    if nd + ((!other) as u64) < best {
        HIT.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        if nd + ((!other) as u64) < u32::MAX as u64 {
            HIT_NARROW.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        }
    }
    best = best.min(nd + (!other) as u64);
}"""
assert source.count(needle) == 1
with tempfile.TemporaryDirectory(prefix="d-prune-search30-") as temp:
    src = pathlib.Path(temp) / "search.rs"
    binary = pathlib.Path(temp) / "search"
    src.write_text(source.replace(needle, replacement) + "\n" + (here / "search-tail.rs").read_text())
    subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C", "overflow-checks=yes",
                    "-C", "debug-assertions=yes", str(src), "-o", str(binary)], check=True)
    subprocess.run([str(binary), "--nocapture", "--test-threads=1"], check=True)

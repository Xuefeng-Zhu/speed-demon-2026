#!/usr/bin/env python3
"""Instrument a frozen guarded-loader source and independently check its CSRs."""
from pathlib import Path
import hashlib
import subprocess
import tempfile

here = Path(__file__).resolve().parent
source_path = here.parent / "track-d-guarded-loader" / "candidate.rs"
source = source_path.read_text()
expected_sha = "77f764359aa3189f73e37d2b411ba80a700ee66ee25a40c0286e658ab45f52d4"
assert hashlib.sha256(source.encode()).hexdigest() == expected_sha


def replace_once(text, old, new):
    assert text.count(old) == 1, (text.count(old), old)
    return text.replace(old, new, 1)


source = replace_once(
    source,
    "    used.fetch_update(Relaxed, Relaxed, |v| v.checked_add(bytes).filter(|&n| n <= LOADER_BUDGET_BYTES)).is_ok()",
    "    let ok = used.fetch_update(Relaxed, Relaxed, |v| v.checked_add(bytes).filter(|&n| n <= LOADER_BUDGET_BYTES)).is_ok();\n"
    "    if ok { TEST_LEDGER.fetch_max(used.load(Relaxed), Relaxed); } ok",
)
source = replace_once(
    source,
    "        Some(graphs) => graphs,\n        None => load_graph_exact(path, threads),",
    "        Some(graphs) => { TEST_FAST.fetch_add(1, Relaxed); graphs },\n"
    "        None => { assert_eq!(TEST_ACTIVE.load(Relaxed), 0, \"fallback before worker joins\"); "
    "TEST_FALLBACK.fetch_add(1, Relaxed); load_graph_exact(path, threads) },",
)
source = replace_once(
    source,
    "            sc.spawn(move || {\n                let result = (|| -> Option<[Vec<Vec<Edge>>; 2]> {",
    "            sc.spawn(move || {\n                let _worker = TestWorker::begin();\n"
    "                let result = (|| -> Option<[Vec<Vec<Edge>>; 2]> {",
)
source = replace_once(
    source,
    "                    if cancelled.load(Relaxed) { return None; }",
    "                    if cancelled.load(Relaxed) { TEST_CANCELLED.fetch_add(1,Relaxed); return None; }",
)
source = replace_once(
    source,
    "                        if seen & 4095 == 0 && cancelled.load(Relaxed) { return None; }",
    "                        if seen & 4095 == 0 && cancelled.load(Relaxed) { TEST_CANCELLED.fetch_add(1,Relaxed); return None; }",
)
source = replace_once(
    source,
    "    if !loader_reserve(used, bytes) { return None; }",
    "    if !loader_reserve(used, bytes) { TEST_BUDGETFAIL.fetch_add(1,Relaxed); return None; }",
)
source = replace_once(
    source,
    "    if !loader_reserve(used, excess) { return None; }",
    "    if !loader_reserve(used, excess) { TEST_BUDGETFAIL.fetch_add(1,Relaxed); return None; }",
)
source = replace_once(
    source,
    "                        if out[0][a].len() >= cap || out[1][b].len() >= cap { return None; }",
    "                        if out[0][a].len() >= cap || out[1][b].len() >= cap { TEST_CAPFAIL.fetch_add(1,Relaxed); return None; }",
)
source = replace_once(
    source,
    "                        out[0][a].push((u,v,w)); out[1][b].push((v,u,w));",
    "                        let (before_a,before_b) = (out[0][a].capacity(),out[1][b].capacity());\n"
    "                        assert!(out[0][a].len() < before_a && out[1][b].len() < before_b);\n"
    "                        out[0][a].push((u,v,w)); out[1][b].push((v,u,w));\n"
    "                        assert_eq!((out[0][a].capacity(),out[1][b].capacity()),(before_a,before_b));\n"
    "                        TEST_FAST_PUSH.fetch_add(1, Relaxed);",
)
source = replace_once(
    source,
    "                        out[0][block(u)].push((u, v, w));\n"
    "                        out[1][block(v)].push((v, u, w));",
    "                        let (a,b)=(block(u),block(v));\n"
    "                        let (before_a,before_b)=(out[0][a].capacity(),out[1][b].capacity());\n"
    "                        assert!(out[0][a].len()<before_a && out[1][b].len()<before_b);\n"
    "                        out[0][a].push((u,v,w)); out[1][b].push((v,u,w));\n"
    "                        assert_eq!((out[0][a].capacity(),out[1][b].capacity()),(before_a,before_b));\n"
    "                        TEST_EXACT_PUSH.fetch_add(1, Relaxed);",
)

budget = "const LOADER_BUDGET_BYTES: usize = 320 * 1024 * 1024;"
cap = "let cap = m / threads / threads * 9 / 8 + 64;"
assert source.count(budget) == 1 and source.count(cap) == 1
tail = (here / "tail.rs").read_text()
variants = [
    ("normal", source),
    ("budget0", source.replace(budget, "const LOADER_BUDGET_BYTES: usize = 0;", 1)),
    ("budget1", source.replace(budget, "const LOADER_BUDGET_BYTES: usize = 1;", 1)),
    ("cap0", source.replace(cap, "let cap = 0;", 1)),
    ("cap1", source.replace(cap, "let cap = 1;", 1)),
]
with tempfile.TemporaryDirectory(prefix="sd-guarded-independent-") as tmp:
    root = Path(tmp)
    for name, text in variants:
        rust = root / (name + ".rs")
        binary = root / name
        rust.write_text(text + "\n" + tail)
        subprocess.run(["rustc", "--edition=2021", "--test", "-O", "-C",
                        "overflow-checks=yes", "-C", "debug-assertions=yes",
                        str(rust), "-o", str(binary)], check=True)
        subprocess.run([str(binary), "--nocapture"], check=True,
                       env={**__import__("os").environ, "SD_TEST_VARIANT": name})

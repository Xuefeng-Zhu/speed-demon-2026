#!/usr/bin/env python3
"""Interleaved parse-phase timing of Track A variants (local diagnostic, stdlib only).

For every --variant NAME=PATH.rs, writes a copy to target/parse-<NAME>.rs that prints the wall
time from just before the parse threads are spawned until they are joined
(`parse_ms=` on stderr) and exits when SD_BREAKDOWN is set, so the summary phase is skipped.
Extra rustc arguments per variant may follow a second `=` (for example
`lines=breakdown.rs=--cfg=mode="lines"`). Outputs are not checked: diagnostic modes of
breakdown.rs deliberately skip work. Rounds run every variant once in shuffled order.
Sources whose parse threads go on to summarize (production after FEAT-003) have no join; for
them the time runs until the first thread leaves the barrier after parsing.
"""
import argparse
import json
import os
import random
import statistics
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FLAGS = ["--edition", "2021", "-C", "opt-level=3", "-C", "codegen-units=1", "-C", "lto=fat",
         "-C", "panic=abort", "-C", "target-cpu=x86-64-v3"]
SPAWN = "    let mut chunks: Vec<Vec<Records>> = thread::scope"
AFTER = "    // An endpoint's position in byte order"
# Layout where the parse threads meet at a barrier and go on to summarize.
SPAWN2 = "    thread::scope(|s| {"
AFTER2 = "                if barrier.wait().is_leader() {"


def build(name, src, extra):
    s = (REPO / src).read_text()
    if s.count(SPAWN) == 1 and s.count(AFTER) == 1:
        s = s.replace(SPAWN, "    let t0 = std::time::Instant::now();\n" + SPAWN)
        s = s.replace(AFTER, '    eprintln!("parse_ms={:.3}", t0.elapsed().as_secs_f64() * 1e3);\n'
                      '    if env::var("SD_BREAKDOWN").is_ok() {\n        std::process::exit(0);\n    }\n'
                      + AFTER)
    else:
        assert s.count(SPAWN2) == 1 and s.count(AFTER2) == 1, f"{src}: markers not found"
        s = s.replace(SPAWN2, "    let t0 = std::time::Instant::now();\n" + SPAWN2)
        s = s.replace(AFTER2, '                if env::var("SD_BREAKDOWN").is_ok() {\n'
                      '                    if barrier.wait().is_leader() {\n'
                      '                        eprintln!("parse_ms={:.3}", t0.elapsed().as_secs_f64() * 1e3);\n'
                      '                        std::process::exit(0);\n                    }\n'
                      '                    loop {\n                        thread::park();\n'
                      '                    }\n                }\n' + AFTER2)
    out = HERE / "target"
    out.mkdir(exist_ok=True)
    (out / f"parse-{name}.rs").write_text(s)
    binary = out / f"parse-{name}"
    subprocess.run(["rustc", *FLAGS, *extra, "-A", "warnings", str(out / f"parse-{name}.rs"),
                    "-o", str(binary)], check=True)
    return binary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--variant", action="append", required=True)
    p.add_argument("--data", default=".data/a-full")
    p.add_argument("--threads", default="8")
    p.add_argument("--runs", type=int, default=31)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--report")
    a = p.parse_args()
    variants = {}
    for v in a.variant:
        name, src, *extra = v.split("=", 2)
        variants[name] = {"source": src, "rustc_extra": extra, "binary": build(name, src, extra)}
    out = REPO / ".out" / "parse-time"
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SD_DATA=str(REPO / a.data), SD_OUT=str(out), SD_THREADS=a.threads,
               SD_BREAKDOWN="1")
    rng, names = random.Random(a.seed), list(variants)
    samples = {n: [] for n in names}
    for _ in range(a.runs + 2):
        rng.shuffle(names)
        for n in names:
            r = subprocess.run([str(variants[n]["binary"])], env=env, capture_output=True,
                               text=True, check=True)
            samples[n].append(float(r.stderr.split("parse_ms=")[1].split()[0]))
    report = {"note": "Local x86 VM parse-phase wall times in ms (first 2 rounds are warmups); "
                      "not official scores.", "threads": a.threads, "seed": a.seed, "variants": {}}
    for n in variants:
        meas = samples[n][2:]
        report["variants"][n] = {"source": variants[n]["source"],
                                 "rustc_extra": variants[n]["rustc_extra"],
                                 "median_ms": statistics.median(meas), "samples_ms": samples[n]}
        print(f"{n:>12} {statistics.median(meas):8.2f} ms")
    if a.report:
        Path(a.report).write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()

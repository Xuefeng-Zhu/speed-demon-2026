#!/usr/bin/env python3
"""Paired ratios between any two variants of one bench.py report (same rounds, stdlib only).

Usage: pairs.py REPORT.json CAND:BASE [CAND:BASE ...] prints, per thread count, the median of the
per-round ratios CAND/BASE and the fraction of rounds CAND was faster. Local x86 VM numbers only.
"""
import json
import statistics
import sys


def main():
    report = json.load(open(sys.argv[1]))
    for pair in sys.argv[2:]:
        cand, base = pair.split(":")
        for t in report["config"]["threads"]:
            rows = [r for r in report["rounds"] if r["threads"] == t and not r["warmup"]]
            ratios = [r["runs"][cand]["wall"] / r["runs"][base]["wall"] for r in rows]
            win = sum(x < 1 for x in ratios) / len(ratios)
            print(f"{cand:>10} / {base:<10} threads {t!s:>7}: median {statistics.median(ratios):.4f}"
                  f" win {100 * win:3.0f}% rounds {len(ratios)}")


if __name__ == "__main__":
    main()

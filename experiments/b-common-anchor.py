#!/usr/bin/env python3
"""Stress Track B with distinct phrases that share a frequent bigram.

This synthetic workload follows the file grammar but deliberately differs from
the official generator distribution. It is not a competition benchmark.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", help="compiled Track B executable")
    parser.add_argument("--baseline", help="optional second executable")
    parser.add_argument("--reference", help="optional official b_index.py")
    parser.add_argument("--documents", type=int, default=1000)
    args = parser.parse_args()
    if args.documents < 1:
        parser.error("--documents must be positive")

    combinations = list(itertools.product("cdefgh", repeat=6))
    phrases = [("a", "b") + suffix for suffix in combinations[:10000]]
    phrases += [("c", "d") + suffix for suffix in combinations[:9000]]
    tokens = list("abcdefgh") * 10
    present = {" ".join(tokens[i:i + 8]) for i in range(len(tokens) - 7)}
    n = args.documents
    first = " ".join(map(str, range(min(10, n))))
    match = f"{n} {n * (n - 1) // 2} {first}\n"
    expected = ("".join(match if " ".join(q) in present else "0 0\n"
                        for q in phrases) + match * 31000).encode("ascii")
    expected_hash = hashlib.sha256(expected).hexdigest()

    with tempfile.TemporaryDirectory(prefix="b-common-anchor-") as tmp:
        root = Path(tmp)
        with (root / "docs.txt").open("w", encoding="ascii", newline="\n") as f:
            text = " ".join(tokens)
            for i in range(n):
                f.write(f"{i}\t{text}\n")
        with (root / "queries.txt").open("w", encoding="ascii", newline="\n") as f:
            for phrase in phrases:
                f.write('PHRASE "' + " ".join(phrase) + '"\n')
            f.write("BOOL a\n" * 31000)

        results = []
        for label, executable in (("candidate", args.candidate),
                                  ("baseline", args.baseline)):
            if not executable:
                continue
            output = root / (label + ".txt")
            start = time.monotonic()
            subprocess.run([str(Path(executable).resolve()), str(root / "docs.txt"),
                            str(root / "queries.txt"), str(output)], check=True)
            elapsed = time.monotonic() - start
            actual = output.read_bytes()
            if actual != expected:
                raise RuntimeError(f"{label} output differs from independent oracle")
            results.append({"name": label, "seconds": round(elapsed, 6),
                            "sha256": hashlib.sha256(actual).hexdigest()})

        if args.reference:
            out_dir = root / "reference"
            subprocess.run([sys.executable, str(Path(args.reference).resolve()),
                            "--data", str(root), "--out", str(out_dir)], check=True)
            if (out_dir / "results.txt").read_bytes() != expected:
                raise RuntimeError("official reference differs from independent oracle")

        print(json.dumps({"documents": n, "tokens_per_document": len(tokens),
                          "distinct_phrases": len(phrases), "bool_queries": 31000,
                          "expected_sha256": expected_hash,
                          "official_reference_checked": bool(args.reference),
                          "results": results}, indent=2))


if __name__ == "__main__":
    main()

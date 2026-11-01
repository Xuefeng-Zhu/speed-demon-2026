#!/usr/bin/env python3
"""Run 55 native correctness checks per shared-dictionary finalist; no timings.

Uses the existing bench-shared-box and bench-shared-inline binaries. Run inside
the pinned native x86 tool image after serialized timing/memory measurements:
    python3 experiments/a-shared-dictionary/verify-native.py
    python3 experiments/a-shared-dictionary/verify-native.py --variants shared-box

Logs go under target/. The JSON report stays non-passing until the selected
source/binary identities and every requested subprocess succeed.
"""

import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


VARIANTS = ("shared-box", "shared-inline")
THREADS = "1,2,3,6,8,16,20,default"
SEEDS = "2,98,999,4242"
ADVERSARIAL_THREADS = "1,2,3,7,12"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", "--variant", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    args = parser.parse_args()
    if len(args.variants) != len(set(args.variants)):
        parser.error("--variants must not contain duplicates")
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        parser.error("requires native Linux x86-64")
    here = Path(__file__).resolve().parent
    root = here.parent.parent
    target = here / "target"
    target.mkdir(parents=True, exist_ok=True)
    report_path = here / "native-correctness.json"
    data = Path("/inputs/full-seed1")
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{os.getpid()}"
    report = {
        "run_id": run_id,
        "execution": "native Linux x86-64; existing pinned-tool-image benchmark binaries",
        "data": str(data),
        "threads": THREADS.split(","),
        "sample_seeds": [int(value) for value in SEEDS.split(",")],
        "adversarial_threads": [int(value) for value in ADVERSARIAL_THREADS.split(",")],
        "expected_checks_per_variant": 55,
        "variants": {},
        "executed_commands": [],
        "complete": False,
        "all_passed": False,
    }

    def save():
        temporary = report_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(report_path)

    def run(stage, command, variant=None, expected_checks=None):
        label = f"{variant}-{stage}" if variant else stage
        log = target / f"verify-{run_id}-{label}.log"
        record = {
            "stage": stage,
            "variant": variant,
            "command": command,
            "cwd": str(root),
            "log": str(log.relative_to(root)),
            "returncode": None,
            "expected_checks": expected_checks,
            "checks_passed": 0,
            "passed": False,
        }
        report["executed_commands"].append(record)
        save()
        print(f"Running {label}; log={record['log']}", flush=True)
        environment = dict(os.environ)
        for variable in ("SD_THREADS", "SD_DATA", "SD_OUT"):
            environment.pop(variable, None)
        with log.open("w") as stream:
            try:
                process = subprocess.run(command, cwd=root, env=environment,
                                         stdout=stream, stderr=subprocess.STDOUT)
                record["returncode"] = process.returncode
            except OSError as error:
                record["error"] = f"{type(error).__name__}: {error}"
                stream.write(record["error"] + "\n")
        text = log.read_text(errors="replace")
        ok_lines = sum(line.startswith("ok  ") for line in text.splitlines())
        record["observed_ok_lines"] = ok_lines
        record["passed"] = record["returncode"] == 0 and (
            expected_checks is None or ok_lines == expected_checks
        )
        if record["passed"] and expected_checks is not None:
            record["checks_passed"] = expected_checks
        if record["returncode"] == 0 and expected_checks is not None and ok_lines != expected_checks:
            record["error"] = f"expected {expected_checks} check results; observed {ok_lines}"
        record["log_sha256"] = sha256(log)
        save()
        print(f"{'PASS' if record['passed'] else 'FAIL'} {label} "
              f"exit={record['returncode']} checks={record['checks_passed']}", flush=True)
        return record

    save()
    try:
        if not (data / "requests.log").is_file():
            raise FileNotFoundError(data / "requests.log")
        for name in args.variants:
            source = here / f"{name}.rs"
            binary = root / "experiments/a-x86-speed/target" / f"bench-{name}"
            report["variants"][name] = {
                "source": str(source.relative_to(root)),
                "source_sha256": sha256(source),
                "native_binary": str(binary.relative_to(root)),
                "native_binary_sha256": sha256(binary),
                "core_checks_passed": 0,
                "adversarial_checks_passed": 0,
                "forced_adversarial_checks_passed": 0,
                "total_checks_passed": 0,
                "passed": False,
            }
        save()
        for name in args.variants:
            binary = root / report["variants"][name]["native_binary"]
            core = run("core", [sys.executable, "-u", str(root / "experiments/a-x86-speed/check.py"),
                                str(binary), "--data", str(data), "--threads", THREADS,
                                "--seeds", SEEDS], name, 15)
            report["variants"][name]["core_checks_passed"] = core["checks_passed"]
            adversarial = run("adversarial", [sys.executable, "-u",
                              str(root / "experiments/a-x86-speed/adversarial.py"),
                              "--binary", str(binary), "--spec", "--threads", ADVERSARIAL_THREADS], name, 20)
            report["variants"][name]["adversarial_checks_passed"] = adversarial["checks_passed"]
            save()

        preparation_command = [sys.executable, "-u", str(here / "prepare-forced.py"), "--build"]
        for name in args.variants:
            preparation_command += ["--source", f"{name}.rs"]
        preparation = run("prepare-forced", preparation_command)
        if preparation["passed"]:
            manifest = json.loads((target / "forced-hash-manifest.json").read_text())
            by_source = {item["candidate"]: item for item in manifest}
            for name in args.variants:
                identity = by_source[f"{name}.rs"]
                if identity["source_sha256"] != report["variants"][name]["source_sha256"]:
                    raise RuntimeError(f"{name}: source changed before forced build")
                forced_binary = target / f"{name}-forced-hash"
                if Path(identity["binary"]).resolve() != forced_binary.resolve():
                    raise RuntimeError(f"{name}: unexpected forced binary path")
                if sha256(forced_binary) != identity["binary_sha256"]:
                    raise RuntimeError(f"{name}: forced binary identity mismatch")
                report["variants"][name]["forced_source_sha256"] = identity["forced_source_sha256"]
                report["variants"][name]["forced_binary_sha256"] = identity["binary_sha256"]
                forced = run("forced-adversarial", [sys.executable, "-u",
                             str(root / "experiments/a-x86-speed/adversarial.py"),
                             "--binary", str(forced_binary), "--spec", "--threads", ADVERSARIAL_THREADS], name, 20)
                report["variants"][name]["forced_adversarial_checks_passed"] = forced["checks_passed"]
                save()

        for name, item in report["variants"].items():
            item["source_unchanged"] = sha256(root / item["source"]) == item["source_sha256"]
            item["native_binary_unchanged"] = sha256(root / item["native_binary"]) == item["native_binary_sha256"]
            steps = [step for step in report["executed_commands"] if step["variant"] == name]
            item["total_checks_passed"] = sum(step["checks_passed"] for step in steps)
            item["passed"] = (
                len(steps) == 3 and all(step["passed"] for step in steps)
                and item["total_checks_passed"] == 55
                and item["source_unchanged"] and item["native_binary_unchanged"]
            )
        report["complete"] = True
        report["all_passed"] = (
            preparation["passed"] and all(item["passed"] for item in report["variants"].values())
            and all(step["returncode"] == 0 for step in report["executed_commands"])
        )
        report["total_checks_passed"] = sum(item["total_checks_passed"] for item in report["variants"].values())
        save()
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        report["all_passed"] = False
        save()
        raise
    print(f"Wrote {report_path}: all_passed={report['all_passed']}; "
          f"checks={report['total_checks_passed']}", flush=True)
    raise SystemExit(0 if report["all_passed"] else 1)


if __name__ == "__main__":
    main()

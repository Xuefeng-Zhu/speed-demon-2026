#!/usr/bin/env python3
"""Native x86 Docker memory pairs; no Docker elapsed time is reported as process T."""

import argparse
import hashlib
import json
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[2]
EXPECTED = "495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3"
REPORT = HERE / "native-memory.json"
VARIANTS = ("baseline", "shared-box", "shared-inline", "shared-box-bounded")
WRAPPER = '/app/solution; rc=$?; printf "\\nsd_peak "; cat /sys/fs/cgroup/memory.peak; exit "$rc"'


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/inputs/full-seed1"),
                        help="native-host directory containing requests.log")
    data = parser.parse_args().data.resolve()
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
        raise SystemExit("requires native Linux x86-64")
    if os.geteuid() != 0:
        raise SystemExit("run with sudo python3 on the native host")
    if docker("ps", "-q"):
        raise SystemExit("refusing to start: Docker already has a running container")
    if not (data / "requests.log").is_file():
        raise SystemExit(f"missing input: {data / 'requests.log'}")
    if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
        raise SystemExit("requires cgroup v2 memory.peak")
    owned = HERE / "target/native-memory"
    owned.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="run-", dir=owned))
    report = {
        "note": "Native container memory evidence, not an official parent-cgroup score. "
                "memory.peak includes the solution, its loader, the shell/cat wrapper, "
                "and charged output/tmpfs pages. Host-warming input before each run "
                "does not reproduce every detail of the competition harness.",
        "host": {"machine": platform.machine(), "kernel": platform.release()},
        "data": str(data), "input_sha256": sha256(data / "requests.log"),
        "expected_output_sha256": EXPECTED,
        "shuffle_seed": 1122, "rounds_per_thread_count": 5,
        "threads": [16, 20], "wrapper": WRAPPER,
        "artifacts": str(run_root.relative_to(REPO)),
        "sources": {}, "images": {}, "runs": [], "summary": {}, "complete": False,
    }

    def save():
        REPORT.write_text(json.dumps(report, indent=2) + "\n")

    try:
        for variant in VARIANTS:
            source = HERE / f"{variant}.rs"
            context = run_root / f"context-{variant}"
            shutil.copytree(REPO / "track-a", context,
                            ignore=shutil.ignore_patterns("target", "__pycache__", ".cache", "cache",
                                                         "*.pyc", ".git", ".env*"))
            shutil.copyfile(source, context / "src/main.rs")
            image = f"sd-a-shared-memory-{variant}"
            command = ["docker", "build", "--network", "none", "--platform", "linux/amd64",
                       "--pull=false", "-t", image, str(context)]
            with (run_root / f"build-{variant}.log").open("w") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            report["sources"][variant] = {"path": str(source.relative_to(REPO)),
                                            "sha256": sha256(source)}
            report["images"][variant] = {
                "tag": image, "id": docker("image", "inspect", "--format", "{{.Id}}", image),
                "dockerfile_sha256": sha256(context / "Dockerfile"),
            }
        save()
        rng = random.Random(1122)
        for threads in (16, 20):
            for number in range(5):
                order = list(VARIANTS)
                rng.shuffle(order)
                for position, variant in enumerate(order):
                    if docker("ps", "-q"):
                        raise RuntimeError("another container is running; stopping before next trial")
                    # Prewarm outside the measured container, matching the warm-input intent.
                    with (data / "requests.log").open("rb") as source:
                        while source.read(8 << 20):
                            pass
                    output = Path(tempfile.mkdtemp(prefix=f"{threads}-{number}-{variant}-",
                                                  dir=run_root))
                    output.chmod(0o777)
                    command = [
                        "docker", "run", "--rm", "--platform", "linux/amd64",
                        "--user", "65534:65534", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges", "--network", "none",
                        "--read-only", "--memory", "8g", "--memory-swap", "8g",
                        "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g",
                        "--mount", f"type=bind,src={data},dst=/data,readonly",
                        "--mount", f"type=bind,src={output},dst=/out",
                        "-e", "SD_DATA=/data", "-e", "SD_OUT=/out",
                        "-e", f"SD_THREADS={threads}", "--entrypoint", "/bin/sh",
                        report["images"][variant]["id"], "-c", WRAPPER,
                    ]
                    result = subprocess.run(command, capture_output=True, text=True)
                    stem = f"{threads}-{number}-{position}-{variant}"
                    (run_root / f"{stem}.stdout.log").write_text(result.stdout)
                    (run_root / f"{stem}.stderr.log").write_text(result.stderr)
                    peak = re.findall(r"^sd_peak ([0-9]+)$", result.stdout, re.MULTILINE)
                    summary = output / "summary.txt"
                    digest = sha256(summary) if summary.is_file() else None
                    row = {"threads": threads, "round": number, "order": order,
                           "position": position, "variant": variant,
                           "exit_code": result.returncode,
                           "peak_bytes": int(peak[0]) if len(peak) == 1 else None,
                           "sha256": digest, "log_stem": stem}
                    report["runs"].append(row)
                    save()
                    if result.returncode or len(peak) != 1 or digest != EXPECTED:
                        raise RuntimeError(f"trial failed: {stem}; inspect saved logs/output")
                    summary.unlink()  # Only this run's verified output file is removed.
                    print(f"threads={threads} round={number} {variant} peak={row['peak_bytes']}",
                          flush=True)
            report["summary"][str(threads)] = {
                variant: {"n": 5, "median_peak_bytes": statistics.median(peaks),
                          "max_peak_bytes": max(peaks)}
                for variant in VARIANTS
                for peaks in [[row["peak_bytes"] for row in report["runs"]
                               if row["threads"] == threads and row["variant"] == variant]]
            }
            save()
        report["all_hashes_ok"] = all(row["sha256"] == EXPECTED for row in report["runs"])
        report["complete"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        save()
        raise
    save()
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()

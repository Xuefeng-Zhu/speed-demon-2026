"""Run correctness properties, an independent x86 screen and a diagnostic probe."""
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[1]
os.chdir(root)
assert platform.machine() == "x86_64"
target = here / "target"
target.mkdir(exist_ok=True)
flags = ["--edition=2021", "--crate-name", "solution", "-C", "opt-level=3", "-C", "lto=fat",
         "-C", "codegen-units=1", "-C", "panic=abort", "-C", "target-cpu=x86-64-v3"]
results = {"properties": {}, "probe": [], "complete": False}

def save():
    (here / "native-validation.json").write_text(json.dumps(results, indent=2) + "\n")

def run(command, label):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (target / f"{label}.log").write_text(result.stdout)
    print(result.stdout[-10000:], end="", flush=True)
    result.check_returncode()
    return result.stdout

host = {"machine": platform.machine(), "kernel": platform.release(),
        "cpu": subprocess.check_output(["lscpu"], text=True),
        "allowed_cpus": sorted(os.sched_getaffinity(0)),
        "cpu_quota": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "rustc": subprocess.check_output(["rustc", "-Vv"], text=True),
        "input_sha256": hashlib.file_digest(Path("/inputs/full-seed1/requests.log").open("rb"), "sha256").hexdigest()}
assert host["input_sha256"] == "7ec80ba45bceef51ac7f79d3a14521fc6187b2dcb87b5e5542d08063fe5d962a"
(here / "native-host.json").write_text(json.dumps(host, indent=2) + "\n")
try:
    for name in ("shared", "simd"):
        output = run([sys.executable, "-u", str(here / f"{name}-property.py")], f"{name}-property")
        results["properties"][name] = {"passed": True, "output": output}
        save()
    run([sys.executable, str(here / "tiny-simd-property.py"), "--emit", str(target / "tiny-property.rs")], "tiny-emit")
    run(["rustc", *flags, "-C", "overflow-checks=yes", str(target / "tiny-property.rs"), "-o", str(target / "tiny-property")], "tiny-build")
    output = run([str(target / "tiny-property")], "tiny-property")
    results["properties"]["tiny-simd"] = {"passed": True, "output": output}
    save()

    command = [sys.executable, "-u", "experiments/a-x86-speed/bench.py"]
    for name in ("baseline", "control", "shared-box", "shared-inline", "simd", "tiny-simd"):
        source = "baseline" if name == "control" else name
        command += ["--variant", f"{name}=experiments/a-shared-dictionary/{source}.rs=--crate-name solution"]
    command += ["--data", "/inputs/full-seed1", "--out", ".out/native-bench", "--threads", "8,16,20",
                "--runs", "31", "--warmup", "2", "--seed", "1120", "--report", str(here / "native-screen.json")]
    run(command, "native-screen")

    run(["rustc", *flags, str(here / "lookahead-probe.rs"), "-o", str(target / "lookahead-probe")], "probe-build")
    output_dir = target / "probe-out"
    output_dir.mkdir(exist_ok=True)
    for threads in (16, 20):
        for trial in range(3):
            environment = {**os.environ, "SD_DATA": "/inputs/full-seed1", "SD_OUT": str(output_dir), "SD_THREADS": str(threads)}
            result = subprocess.run([str(target / "lookahead-probe")], env=environment, capture_output=True, text=True, check=True)
            digest = hashlib.sha256((output_dir / "summary.txt").read_bytes()).hexdigest()
            assert digest == "495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3"
            results["probe"].append({"threads": threads, "trial": trial, "diagnostic": result.stderr.strip(), "sha256": digest})
            print(f"probe threads={threads} {result.stderr.strip()}", flush=True)
            save()
    results["complete"] = True
except BaseException as error:
    results["error"] = f"{type(error).__name__}: {error}"
    save()
    raise
save()

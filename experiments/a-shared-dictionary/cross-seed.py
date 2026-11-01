"""Native paired comparisons on two independently generated full datasets."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[1]
os.chdir(root)
target = here / "target"
output = target / "cross-seed-baseline"
output.mkdir(parents=True, exist_ok=True)
results = {}
for seed in (2, 3):
    data = Path(f"/inputs/full-seed{seed}")
    subprocess.run([str(root / "experiments/a-x86-speed/target/bench-baseline")],
                   env={**os.environ, "SD_DATA": str(data), "SD_OUT": str(output), "SD_THREADS": "16"}, check=True)
    expected = hashlib.sha256((output / "summary.txt").read_bytes()).hexdigest()
    with (data / "requests.log").open("rb") as stream:
        input_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    results[str(seed)] = {"input_sha256": input_hash, "expected_output_sha256": expected,
                          "expected_source": "captured production baseline, executed on the same input"}
    command = [sys.executable, "-u", "experiments/a-x86-speed/bench.py"]
    for name in ("baseline", "control", "shared-box", "shared-inline"):
        source = "baseline" if name == "control" else name
        command += ["--variant", f"{name}=experiments/a-shared-dictionary/{source}.rs=--crate-name solution"]
    command += ["--data", str(data), "--out", ".out/native-bench", "--threads", "16,20",
                "--runs", "21", "--warmup", "2", "--seed", str(1122 + seed),
                "--expected", expected, "--report", str(here / f"native-seed{seed}.json")]
    subprocess.run(command, check=True)
    (here / "cross-seed-inputs.json").write_text(json.dumps(results, indent=2) + "\n")

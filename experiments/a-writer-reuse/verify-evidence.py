"""Check retained experiment integrity and source identity; runs no solution workload."""
import hashlib
import json
from pathlib import Path
import tarfile

here = Path(__file__).resolve().parent
root = here.parents[1]
summary = json.loads((here / "summary.json").read_text())
archive = here / "evidence.tar.gz"
sha = lambda data: hashlib.sha256(data).hexdigest()
assert sha(archive.read_bytes()) == summary["archive_sha256"]
prefix = "experiments/a-profile-experiments-20261101/"
with tarfile.open(archive, "r:gz") as stream:
    files = {}
    for member in stream.getmembers():
        path = Path(member.name)
        assert member.isfile() and not path.is_absolute() and ".." not in path.parts
        assert member.name.startswith(prefix) and member.name not in files
        files[member.name] = stream.extractfile(member).read()

read = lambda name: json.loads(files[prefix + "results/" + name + ".json"])
manifest = json.loads(files[prefix + "manifest.json"])
for name, digest in manifest["files"].items():
    assert sha(files[prefix + name]) == digest, name
candidate_sha = summary["candidate_source_sha256"]
assert sha((root / "track-a/src/main.rs").read_bytes()) == candidate_sha
assert sha(files[prefix + "reserved-reuse-4.rs"]) == candidate_sha
assert sha(files[prefix + "baseline.rs"]) == summary["baseline_source_sha256"]

total = warmup = 0
reports = ["screen", "confirm-seed1", "confirm-seed2", "confirm-seed3",
           "blocks-seed1", "blocks-seed2", "blocks-seed3", "cap-screen-seed1",
           "cap-confirm-seed2", "cap-confirm-seed3"]
for name in reports:
    report = read(name)
    assert report["all_hashes_ok"]
    expected = report["expected_output_sha256"]
    for row in report.get("rounds", report.get("pairs", [])):
        samples = list(row["runs"].values()) if "runs" in row else [
            run for side in row["samples"].values() for run in side]
        assert all(run["sha256"] == expected for run in samples), name
        total += len(samples)
        warmup += len(samples) if row["warmup"] else 0
assert total == 11516 and warmup == 664
assert summary["timed_output_validation"]["timed_outputs"] == total
binary_ids = set()
for seed in (1, 2, 3):
    report = read("cap-screen-seed1" if seed == 1 else f"cap-confirm-seed{seed}")
    candidate = report["sources"]["reserved-reuse-4"]
    assert candidate["source_sha256"] == candidate_sha
    assert summary["candidate"][str(seed)]["source"] == candidate
    binary_ids.add(candidate["binary_sha256"])
assert len(binary_ids) == 1

correctness = read("correctness-cap4")
assert correctness["complete"] and correctness["all_passed"]
assert all(stage["passed"] for stage in correctness["stages"])
candidate = correctness["variants"]["reserved-reuse-4"]
assert candidate["source_sha256"] == candidate_sha and candidate["checks_passed"] == 55
assert summary["correctness"] == correctness
memory_runs = 0
for name in ("memory", "memory-caps"):
    report = read(name)
    assert report["complete"] and report["all_hashes_ok"]
    assert all(run["sha256"] == report["expected_output_sha256"] for run in report["runs"])
    memory_runs += len(report["runs"])
assert memory_runs == 60
assert summary["memory"] == read("memory-caps")["summary"]
print(f"PASS: archive/source integrity, {total} timed hashes ({warmup} warmups), "
      f"{memory_runs} memory outputs, and 55 selected-source check groups")

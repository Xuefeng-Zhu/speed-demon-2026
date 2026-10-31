#!/usr/bin/env python3
"""Track A x86 profile driver (local diagnostics only, not official scoring).

Builds baseline.rs (exact production copy), profile.rs (instrumented copy) and io-probe.rs with
production-equivalent rustc flags, generates the full seed-1 input if it is missing, then
interleaves baseline/profile runs per thread count, checks every output SHA-256, captures child
rusage via os.wait4, parses the profile's stderr key value lines, runs the io-probe modes with
the same interleaving, and writes raw samples plus medians/means to a JSON report.
"""
import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EXPECTED = "495ca09682b9673ef836a506496177680bb4a3af54255174befddb1f83481cd3"
INPUT_SHA = "7ec80ba45bceef51ac7f79d3a14521fc6187b2dcb87b5e5542d08063fe5d962a"
RUSTFLAGS = ["--edition", "2021", "-C", "opt-level=3", "-C", "codegen-units=1", "-C", "lto=fat",
             "-C", "panic=abort", "-C", "target-cpu=x86-64-v3"]
PROBE_MODES = [("mmap-touch", None), ("mmap-sum", None), ("mmap-nodontneed-touch", None),
               ("mmap-nodontneed-sum", None), ("mmap-populate-sum", None),
               ("pread", 64), ("pread", 256), ("pread", 1024)]
LIST_KINDS = {"parse_thread", "summary_worker", "thread", "hour_job"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cmd_out(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        return f"unavailable: {e}"


def value(v):
    for conv in (int, float):
        try:
            return conv(v)
        except ValueError:
            pass
    return v


def parse_lines(text):
    """`kind [name] key=value ...` lines into {kind: {name: fields}} or {kind: [fields]}."""
    out = {}
    for line in text.splitlines():
        tok = line.split()
        if not tok:
            continue
        kind, rest, name = tok[0], tok[1:], None
        if rest and "=" not in rest[0]:
            name, rest = rest[0], rest[1:]
        fields = {k: value(v) for k, v in (t.split("=", 1) for t in rest if "=" in t)}
        if kind in LIST_KINDS:
            fields["name"] = value(name) if name is not None else None
            out.setdefault(kind, []).append(fields)
        elif name is not None:
            out.setdefault(kind, {})[name] = fields
        else:
            out[kind] = fields
    return out


def spawn(argv, env):
    """Runs argv, returns (wall seconds, rusage dict, stderr text)."""
    with tempfile.TemporaryFile() as err:
        t0 = time.perf_counter()
        proc = subprocess.Popen(argv, env=env, stdout=subprocess.DEVNULL, stderr=err)
        _, status, ru = os.wait4(proc.pid, 0)
        wall = time.perf_counter() - t0
        proc.returncode = os.waitstatus_to_exitcode(status)
        err.seek(0)
        text = err.read().decode()
    if proc.returncode != 0:
        raise SystemExit(f"{argv} exited {proc.returncode}: {text[-2000:]}")
    usage = {"utime": ru.ru_utime, "stime": ru.ru_stime, "minflt": ru.ru_minflt,
             "majflt": ru.ru_majflt, "maxrss_kib": ru.ru_maxrss, "nvcsw": ru.ru_nvcsw,
             "nivcsw": ru.ru_nivcsw}
    return wall, usage, text


def run_solution(binary, data, out, threads, sample_us=None):
    summary = Path(out) / "summary.txt"
    summary.unlink(missing_ok=True)
    env = dict(os.environ, SD_DATA=str(data), SD_OUT=str(out), SD_THREADS=str(threads))
    env.pop("SD_PROFILE_SAMPLE_US", None)
    if sample_us:
        env["SD_PROFILE_SAMPLE_US"] = str(sample_us)
    wall, usage, err = spawn([str(binary)], env)
    digest = sha256(summary)
    if digest != EXPECTED:
        raise SystemExit(f"hash mismatch {binary} threads={threads}: {digest}")
    return {"wall": wall, **usage, "sha256": digest, "ok": True,
            "out_bytes": summary.stat().st_size, "stderr": err}


def derive(run, input_bytes):
    """Per-run derived metrics from the profile's parsed stderr."""
    p = run["profile"]
    ph = p["phase"]
    d = {}

    def delta(a, b, k):
        return ph[b][k] - ph[a][k]

    d["t_mapped"] = ph["mapped"]["t"]
    d["t_parse_done"] = ph["parse_done"]["t"]
    d["t_merge_done"] = ph["merge_done"]["t"]
    d["t_first_written"] = ph["first_written"]["t"]
    d["t_summary_done"] = p["summary_done"]["t"]
    d["t_done"] = ph["done"]["t"]
    d["parse"] = delta("cuts", "parse_done", "t")
    d["setup"] = ph["cuts"]["t"]
    d["merge"] = delta("parse_done", "merge_done", "t")
    d["gap_merge_to_first_recv"] = p["writes"]["first_recv"] - ph["merge_done"]["t"]
    d["gap_merge_to_first_written"] = delta("merge_done", "first_written", "t")
    # Head-of-line decomposition of the gap: first receipt (any hour), then waiting for hour 0,
    # then hour 0's write_all.
    w = p["writes"]
    d["first_hour"] = w["first_hour"]
    d["held_before_hour0"] = w["held_before_hour0"]
    d["gap_first_recv_to_hour0_recv"] = w["hour0_recv"] - w["first_recv"]
    d["gap_hour0_recv_to_first_written"] = ph["first_written"]["t"] - w["hour0_recv"]
    d["first_write"] = w["first_write"]
    jobs = {j["name"]: j for j in p["hour_job"]}
    h0 = jobs[0]
    d["hour0_start_after_merge"] = h0["t_start"] - ph["merge_done"]["t"]
    d["hour0_dur"] = h0["dur"]
    d["hour0_records"] = h0["records"]
    first_wave = [jobs[h] for h in range(1, len(p["summary_worker"])) if h in jobs]
    if first_wave:
        d["first_wave_other_dur_median"] = statistics.median(j["dur"] for j in first_wave)
        d["first_wave_other_records_median"] = statistics.median(j["records"] for j in first_wave)
    d["hour_dur_median"] = statistics.median(j["dur"] for j in jobs.values())
    d["hour_records_median"] = statistics.median(j["records"] for j in jobs.values())
    d["summary_write"] = delta("merge_done", "done", "t")
    d["after_summary_done"] = ph["done"]["t"] - p["summary_done"]["t"]
    d["outside_main"] = run["wall"] - ph["done"]["t"]
    for name, a, b in [("parse", "cuts", "parse_done"), ("merge", "parse_done", "merge_done"),
                       ("summary_write", "merge_done", "done"), ("total", "start", "done")]:
        for k in ("cpu", "utime", "stime", "minflt", "majflt", "nivcsw"):
            d[f"{name}_{k}"] = delta(a, b, k)
    th = p["parse_thread"]
    mib = input_bytes / (1 << 20)
    d["parse_threads"] = len(th)
    d["parse_thread_wall_max"] = max(t["wall"] for t in th)
    d["parse_thread_wall_min"] = min(t["wall"] for t in th)
    d["parse_thread_end_spread"] = max(t["t_end"] for t in th) - min(t["t_end"] for t in th)
    d["parse_thread_start_spread"] = max(t["t_start"] for t in th) - min(t["t_start"] for t in th)
    d["parse_thread_cpu_sum"] = sum(t["cpu"] for t in th)
    d["parse_thread_user_sum"] = sum(t["user"] for t in th)
    d["parse_thread_sys_sum"] = sum(t["sys"] for t in th)
    d["parse_thread_minflt_sum"] = sum(t["minflt"] for t in th)
    d["parse_thread_minflt_per_thread"] = d["parse_thread_minflt_sum"] / len(th)
    d["parse_minflt_per_mib"] = d["parse_thread_minflt_sum"] / mib
    d["madv_wall_max"] = max(t["madv_wall"] for t in th)
    d["madv_wall_sum"] = sum(t["madv_wall"] for t in th)
    d["madv_cpu_sum"] = sum(t["madv_cpu"] for t in th)
    d["madv_sys_sum"] = sum(t["madv_sys"] for t in th)
    sw = p["summary_worker"]
    d["summary_workers"] = len(sw)
    d["summary_cpu_sum"] = sum(t["cpu"] for t in sw)
    d["summary_busy_sum"] = sum(t["busy"] for t in sw)
    d["summary_minflt_sum"] = sum(t["minflt"] for t in sw)
    d["summary_lat_cap_bytes_sum"] = sum(t["lat_cap_bytes"] for t in sw)
    d["write_all_total"] = p["writes"]["total"]
    d["write_bytes"] = p["writes"]["bytes"]
    d["held_max"] = p["writes"]["held_max"]
    d["held_cap_bytes_max"] = p["writes"]["held_cap_bytes_max"]
    for k in ("count", "escapes", "rec_bytes", "rec_cap_bytes", "esc_cap_bytes", "buckets"):
        d[f"records_{k}"] = p["records"][k]
    for at in ("parse_done", "first_written", "done"):
        for k in ("VmRSS", "VmHWM", "RssAnon", "RssFile", "RssShmem", "VmData"):
            d[f"mem_{at}_{k}_kib"] = p["mem"][at][k]
    if "sampler" in p:
        for k, v in p["sampler"].items():
            d[f"sampler_{k}"] = v
    return d


def stats(rows):
    keys = [k for k in rows[0] if all(isinstance(r.get(k), (int, float)) for r in rows)]
    return {k: {"median": statistics.median(r[k] for r in rows),
                "mean": statistics.fmean(r[k] for r in rows),
                "min": min(r[k] for r in rows), "max": max(r[k] for r in rows)} for k in keys}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="/tmp/a-full")
    ap.add_argument("--out", default="/tmp/a-x86-out", help="output dir, keep it on tmpfs")
    ap.add_argument("--runs", type=int, default=7)
    ap.add_argument("--sampled-runs", type=int, default=3,
                    help="extra profile runs per thread count with the RSS sampler on")
    ap.add_argument("--sample-us", type=int, default=200)
    ap.add_argument("--threads", default="6,8,12")
    ap.add_argument("--report", default=str(HERE / "report.json"))
    args = ap.parse_args()
    threads_list = [int(t) for t in args.threads.split(",")]

    data, out = Path(args.data), Path(args.out)
    log = data / "requests.log"
    if not log.exists():
        subprocess.run([sys.executable, str(REPO / "official/generators/a_ingest.py"), "--seed", "1",
                        "--scale", "full", "--out", str(data)], check=True)
    input_bytes = log.stat().st_size
    input_sha = sha256(log)
    if input_sha != INPUT_SHA:
        print(f"warning: input sha256 {input_sha} is not the full seed-1 input", file=sys.stderr)
    out.mkdir(parents=True, exist_ok=True)

    build = HERE / "target"
    build.mkdir(exist_ok=True)
    bins = {}
    for name in ("baseline", "profile", "io-probe"):
        bins[name] = build / name
        subprocess.run(["rustc", *RUSTFLAGS, "-o", str(bins[name]), str(HERE / f"{name}.rs")],
                       check=True)

    host = {
        "cpu_model": next((l.split(":", 1)[1].strip() for l in cmd_out(["lscpu"]).splitlines()
                           if l.startswith("Model name")), "unknown"),
        "nproc": os.cpu_count(),
        "kernel": platform.release(),
        "rustc": cmd_out(["rustc", "-V"]),
        "python": platform.python_version(),
        "data_fs": cmd_out(["stat", "-f", "-c", "%T", str(data)]),
        "out_fs": cmd_out(["stat", "-f", "-c", "%T", str(out)]),
    }
    report = {
        "note": "Local diagnostic measurements on a shared VM; not official, not cgroup memory.",
        "host": host,
        "input": {"path": str(log), "bytes": input_bytes, "sha256": input_sha},
        "expected_output_sha256": EXPECTED,
        "sources": {n: sha256(HERE / f"{n}.rs") for n in ("baseline", "profile", "io-probe")},
        "production_sha256": sha256(REPO / "track-a/src/main.rs"),
        "rustc_flags": RUSTFLAGS,
        "config": {"runs": args.runs, "sampled_runs": args.sampled_runs,
                   "sample_us": args.sample_us, "threads": threads_list},
        "warmup": [], "runs": [], "probe": [], "summary": {},
    }

    def solution(kind, threads, i, sample_us=None):
        r = run_solution(bins["profile" if kind != "baseline" else "baseline"], data, out, threads,
                         sample_us)
        r.update(binary=kind, threads=threads, iter=i)
        err = r.pop("stderr")
        if kind != "baseline":
            r["profile"] = parse_lines(err)
            r["derived"] = derive(r, input_bytes)
        return r

    def probe(mode, buf, threads, i):
        argv = [str(bins["io-probe"]), str(log), str(threads), mode] + ([str(buf)] if buf else [])
        wall, usage, err = spawn(argv, dict(os.environ))
        parsed = parse_lines(err)
        return {"mode": mode if buf is None else f"pread-{buf}k", "threads": threads, "iter": i,
                "wall": wall, **usage, "probe": parsed["probe"][mode], "thread": parsed["thread"]}

    for t in threads_list:
        report["warmup"].append(solution("baseline", t, -1))
        report["warmup"].append(solution("profile", t, -1))
    for t in threads_list:
        for i in range(args.runs):
            order = ["baseline", "profile"] if i % 2 == 0 else ["profile", "baseline"]
            for kind in order:
                report["runs"].append(solution(kind, t, i))
        for i in range(args.sampled_runs):
            report["runs"].append(solution("profile-sampled", t, i, args.sample_us))
        print(f"threads {t}: solution runs done", file=sys.stderr)

    for t in threads_list:
        probe("mmap-sum", None, t, -1)
        for i in range(args.runs):
            k = i % len(PROBE_MODES)
            for mode, buf in PROBE_MODES[k:] + PROBE_MODES[:k]:
                report["probe"].append(probe(mode, buf, t, i))
        print(f"threads {t}: probe runs done", file=sys.stderr)
    # Words are summed from each chunk's start, so checksums agree within one thread count.
    sums = {(p["threads"], p["probe"]["checksum"]) for p in report["probe"]
            if p["mode"] not in ("mmap-touch", "mmap-nodontneed-touch")}
    report["probe_sum_checksums_agree"] = len(sums) == len(threads_list)

    s = report["summary"]
    for t in threads_list:
        for kind in ("baseline", "profile", "profile-sampled"):
            rows = [r for r in report["runs"] if r["binary"] == kind and r["threads"] == t]
            if not rows:
                continue
            key = f"{kind}/{t}"
            s[key] = {"n": len(rows), "all_hashes_ok": all(r["sha256"] == EXPECTED for r in rows),
                      "process": stats([{k: r[k] for k in ("wall", "utime", "stime", "minflt",
                                                           "majflt", "maxrss_kib", "nvcsw",
                                                           "nivcsw", "out_bytes")} for r in rows])}
            if kind != "baseline":
                s[key]["derived"] = stats([r["derived"] for r in rows])
        for mode in dict.fromkeys(p["mode"] for p in report["probe"]):
            rows = [p for p in report["probe"] if p["mode"] == mode and p["threads"] == t]
            flat = []
            for p in rows:
                th = p["thread"]
                flat.append({"wall": p["wall"], "utime": p["utime"], "stime": p["stime"],
                             "minflt": p["minflt"], "maxrss_kib": p["maxrss_kib"],
                             **{k: p["probe"][k] for k in ("map_wall", "read_wall", "total", "cpu",
                                                           "VmHWM", "RssAnon", "RssFile",
                                                           "RssShmem")},
                             "thread_wall_max": max(x["wall"] for x in th),
                             "thread_cpu_sum": sum(x["cpu"] for x in th),
                             "thread_minflt_sum": sum(x["minflt"] for x in th),
                             "madv_wall_max": max(x["madv_wall"] for x in th),
                             "madv_cpu_sum": sum(x["madv_cpu"] for x in th)})
            s[f"probe/{mode}/{t}"] = {"n": len(rows), "stats": stats(flat)}

    report["all_hashes_ok"] = all(r["sha256"] == EXPECTED for r in report["runs"] + report["warmup"])
    Path(args.report).write_text(json.dumps(report, indent=1) + "\n")
    print(f"wrote {args.report}; all hashes ok: {report['all_hashes_ok']}; probe checksums agree: "
          f"{report['probe_sum_checksums_agree']}", file=sys.stderr)
    if not (report["all_hashes_ok"] and report["probe_sum_checksums_agree"]):
        sys.exit(1)


if __name__ == "__main__":
    main()

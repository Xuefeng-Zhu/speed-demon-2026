// Runs each binary RUNS times, interleaved, under `taskset -c CPUS`, and reports the
// distribution of pages allocated per run (system-wide /proc/vmstat deltas) and the huge
// pages installed. A run that allocates 400 or more pages above the binary's own median
// probably discarded at least one 2 MiB huge page (512 pages); background activity on the
// machine also lands here, so compare against a binary that uses no huge pages.
//
//   rustc -O vmdelta.rs && SD_DATA=... SD_OUT=... ./vmdelta 150 0-7 ./a ./b
use std::{collections::HashMap, fs, process::Command};

fn vm() -> HashMap<String, i64> {
    let text = fs::read_to_string("/proc/vmstat").unwrap();
    let pairs = text.lines().map(|l| {
        let mut f = l.split_whitespace();
        (f.next().unwrap().to_string(), f.next().unwrap().parse().unwrap())
    });
    pairs.collect()
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let (runs, cpus) = (a[1].parse::<usize>().unwrap(), a[2].clone());
    let bins = &a[3..];
    let mut res: Vec<Vec<(i64, i64)>> = vec![vec![]; bins.len()];
    for _ in 0..runs {
        for (i, b) in bins.iter().enumerate() {
            let v0 = vm();
            let status = Command::new("taskset").args(["-c", &cpus, b]).status();
            assert!(status.unwrap().success());
            let v1 = vm();
            let d = |k: &str| v1.get(k).unwrap_or(&0) - v0.get(k).unwrap_or(&0);
            let kinds = ["pgalloc_dma", "pgalloc_dma32", "pgalloc_normal", "pgalloc_movable"];
            res[i].push((kinds.iter().map(|k| d(k)).sum(), d("thp_fault_alloc")));
        }
    }
    for (i, b) in bins.iter().enumerate() {
        let mut x: Vec<i64> = res[i].iter().map(|r| r.0).collect();
        x.sort();
        let (med, n) = (x[x.len() / 2], x.len());
        let big = x.iter().filter(|&&v| v >= med + 400).count();
        let thp: i64 = res[i].iter().map(|r| r.1).sum();
        println!(
            "{b}: pages per run p10 {} median {med} p90 {} max {}; huge pages installed {thp}; runs >= median + 400: {big}/{n}",
            x[n / 10],
            x[n * 9 / 10],
            x[n - 1]
        );
    }
}

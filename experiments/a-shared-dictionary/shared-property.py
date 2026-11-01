#!/usr/bin/env python3
"""Native x86 properties for the exact shared dictionary sources, without timing claims.

Default: compile and test shared-box.rs and shared-inline.rs. Select one with
--source shared-box.rs. Run in the pinned native Linux x86 Rust tool image.
Only the original main is renamed; the complete candidate source is preserved.
"""

import argparse
import hashlib
import platform
import subprocess
import tempfile
from pathlib import Path


TAIL = r'''
struct PropertyInput {
    bytes: Vec<u8>,
    start: usize,
    len: usize,
}

fn property_dictionary() -> Dictionary {
    Dictionary {
        slots: (0..4096).map(|_| OnceLock::new()).collect(),
        next_id: AtomicU32::new(0),
    }
}

fn property_input(name: &[u8], offset: usize, fill: u8) -> PropertyInput {
    let mut bytes = vec![fill; offset + name.len() + 128];
    bytes[offset..offset + name.len()].copy_from_slice(name);
    PropertyInput { bytes, start: offset, len: name.len() }
}

fn property_populated(dictionary: &Dictionary) -> usize {
    dictionary.slots.iter().filter(|slot| slot.get().is_some()).count()
}

fn property_same_key() {
    let dictionary = property_dictionary();
    let barrier = Barrier::new(32);
    let name = b"/same-key/discovered-concurrently/{id}";
    let ids: Vec<u32> = thread::scope(|scope| {
        let mut handles = Vec::new();
        for t in 0..32 {
            let (dictionary, barrier) = (&dictionary, &barrier);
            handles.push(scope.spawn(move || {
                let mut input = property_input(name, t % 32, b'X');
                let h = hash(&input.bytes, input.start, input.len);
                barrier.wait();
                let id = dictionary.find(&input.bytes, h, input.start, input.start + input.len);
                for _ in 0..32 {
                    assert_eq!(dictionary.find(&input.bytes, h, input.start, input.start + input.len), id);
                }
                input.bytes.fill(b'Z');
                id
            }));
        }
        handles.into_iter().map(|handle| handle.join().unwrap()).collect()
    });
    assert!(ids.iter().all(|&id| id == 0));
    assert_eq!(dictionary.next_id.load(Ordering::Relaxed), 1);
    assert_eq!(property_populated(&dictionary), 1);
    let entry = dictionary.slots.iter().filter_map(OnceLock::get).next().unwrap();
    assert_eq!(&entry.name[..entry.len as usize], name);
    assert!(entry.name[entry.len as usize..].iter().all(|&byte| byte == 0));
}

fn property_catalogue_collision() {
    const COUNT: usize = 1842;
    const WORKERS: usize = 16;
    // All multipliers are coprime to 1842 = 2 * 3 * 307, giving complete but
    // differently ordered catalogues at the simultaneous discovery boundary.
    const MULTIPLIERS: [usize; WORKERS] = [1, 5, 7, 11, 13, 17, 19, 23, 25, 29, 31, 35, 37, 41, 43, 47];
    let dictionary = property_dictionary();
    let mut inputs: Vec<PropertyInput> = (0..COUNT).map(|id| {
        let name = format!("/{id:0124}");
        assert_eq!(name.len(), 125);
        property_input(name.as_bytes(), id % 32, b'Q')
    }).collect();
    let expected: Vec<Vec<u8>> = inputs.iter()
        .map(|input| input.bytes[input.start..input.start + input.len].to_vec()).collect();
    let barrier = Barrier::new(WORKERS);
    let rows: Vec<Vec<u32>> = thread::scope(|scope| {
        let mut handles = Vec::new();
        for t in 0..WORKERS {
            let (dictionary, barrier, inputs) = (&dictionary, &barrier, &inputs);
            handles.push(scope.spawn(move || {
                let mut ids = vec![u32::MAX; COUNT];
                barrier.wait();
                for position in 0..COUNT {
                    let index = (position * MULTIPLIERS[t] + 97 * t) % COUNT;
                    let input = &inputs[index];
                    assert_eq!(ids[index], u32::MAX, "permutation repeated a key");
                    ids[index] = dictionary.find(&input.bytes, 0, input.start, input.start + input.len);
                }
                ids
            }));
        }
        handles.into_iter().map(|handle| handle.join().unwrap()).collect()
    });
    assert!(rows.iter().all(|row| row == &rows[0]), "threads disagree on key IDs");
    assert_eq!(dictionary.next_id.load(Ordering::Relaxed) as usize, COUNT);
    assert_eq!(property_populated(&dictionary), COUNT);
    let mut sorted_ids = rows[0].clone();
    sorted_ids.sort_unstable();
    assert_eq!(sorted_ids, (0..COUNT as u32).collect::<Vec<_>>(), "IDs are not a dense bijection");
    let mut by_id = vec![Vec::new(); COUNT];
    for (index, &id) in rows[0].iter().enumerate() {
        by_id[id as usize] = expected[index].clone();
    }
    for entry in dictionary.slots.iter().filter_map(OnceLock::get) {
        assert_eq!(entry.hash, 0);
        assert_eq!(entry.len, 125);
        assert_eq!(&entry.name[..125], by_id[entry.id as usize].as_slice());
        assert_eq!(&entry.name[125..], &[0; 3]);
    }

    // Borrow names through the actual summary-plan builder before destroying the
    // input buffers. The plan's references must belong to the immutable dictionary.
    let parsed = vec![Mutex::new(vec![(Vec::new(), Vec::new()); HOURS])];
    let (order, names, jobs) = make_plan(&dictionary, &parsed);
    for input in &mut inputs { input.bytes.fill(b'Z'); }
    drop(inputs);
    assert_eq!(names.len(), COUNT);
    for (rank, name) in names.iter().enumerate() {
        assert_eq!(*name, expected[rank].as_slice(), "borrowed name changed after input destruction");
        assert_eq!(*name, by_id[order[rank] as usize].as_slice());
    }
    assert_eq!(jobs.into_inner().unwrap().count(), HOURS);
}

fn property_lengths_and_mismatches() {
    let mut names = std::collections::BTreeSet::new();
    for len in 1..=125 {
        let mut name = vec![b'a'; len];
        name[0] = b'/';
        names.insert(name.clone());
        if len >= 3 {
            name[len / 2] = b'B';
            names.insert(name);
        }
    }
    // Same length, prefix and suffix, with each interior byte independently
    // mismatched. This covers both halves of the long AVX2 equality comparison.
    for byte in 1..125 {
        let mut name = vec![b'a'; 125];
        name[0] = b'/';
        name[byte] = b'B';
        names.insert(name);
    }
    let expected: Vec<Vec<u8>> = names.into_iter().collect();
    let mut inputs: Vec<_> = expected.iter().enumerate()
        .map(|(index, name)| property_input(name, index % 32, b'R')).collect();
    let dictionary = property_dictionary();
    // A single bucket at the end of the table forces both collisions and wrap.
    let h = 4095u64 << 40;
    let mut ids = Vec::new();
    for input in &inputs {
        ids.push(dictionary.find(&input.bytes, h, input.start, input.start + input.len));
    }
    assert_eq!(dictionary.next_id.load(Ordering::Relaxed) as usize, expected.len());
    assert_eq!(property_populated(&dictionary), expected.len());
    for index in (0..inputs.len()).rev() {
        let input = &inputs[index];
        assert_eq!(dictionary.find(&input.bytes, h, input.start, input.start + input.len), ids[index]);
    }
    let parsed = vec![Mutex::new(vec![(Vec::new(), Vec::new()); HOURS])];
    let (order, names, _) = make_plan(&dictionary, &parsed);
    for input in &mut inputs { input.bytes.fill(b'Z'); }
    drop(inputs);
    assert_eq!(names.len(), expected.len());
    for (rank, name) in names.iter().enumerate() {
        assert_eq!(*name, expected[rank].as_slice());
        assert_eq!(order[rank], ids[rank]);
    }
}

fn main() {
    property_same_key();
    property_catalogue_collision();
    property_lengths_and_mismatches();
    println!("PASS same-key discovery, 1842 forced-collision keys/16 threads, ID bijection, lengths/mismatches/wrap and borrowed-name ownership");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", help="source filename in this directory; repeatable")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise SystemExit("requires native Linux x86-64 with x86-64-v3 CPU features")
    features = Path("/proc/cpuinfo").read_text().lower().split()
    if "avx2" not in features:
        raise SystemExit("CPU must report AVX2")
    here = Path(__file__).resolve().parent
    sources = args.source or ["shared-box.rs", "shared-inline.rs"]
    flags = ["--edition=2021", "-C", "opt-level=3", "-C", "lto=fat", "-C",
             "codegen-units=1", "-C", "panic=abort", "-C", "target-cpu=x86-64-v3",
             "--crate-name", "shared_property", "-A", "dead_code"]
    with tempfile.TemporaryDirectory(prefix="a-shared-property-") as directory:
        temporary = Path(directory)
        for filename in sources:
            if Path(filename).name != filename or not filename.endswith(".rs"):
                raise SystemExit("--source must be a .rs filename in this directory")
            path = here / filename
            source = path.read_text()
            assert source.count("fn main() {") == 1
            exact = source.replace("fn main() {", "fn solution_main() {", 1)
            program, binary = temporary / "main.rs", temporary / "property"
            program.write_text(exact + TAIL)
            print(f"{filename} source_sha256={hashlib.sha256(source.encode()).hexdigest()}", flush=True)
            subprocess.run(["rustc", *flags, str(program), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()

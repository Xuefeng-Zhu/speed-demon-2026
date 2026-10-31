#!/usr/bin/env python3
"""Compile the exact batch implementation plus property tests, normal and forced collisions."""
import pathlib, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parent
candidate=(root/'candidate.rs').read_text(); tests=(root/'property-tail.rs').read_text()
with tempfile.TemporaryDirectory(prefix='b-batch-property-') as temp:
    for forced in (False,True):
        source=candidate
        if forced:
            start=source.index('    fn short_hash(mut x: u64) -> usize {')
            end=source.index('\n    }',start)+6
            source=source[:start]+'    fn short_hash(_x: u64) -> usize { 0 }\n'+source[end:]
        path=pathlib.Path(temp)/('forced.rs' if forced else 'normal.rs'); binary=path.with_suffix('')
        path.write_text(source+'\n'+tests)
        subprocess.run(['rustc','--edition=2021','--test','-C','opt-level=2','-C','overflow-checks=yes',str(path),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
print('PASS exact batch source, normal and all-short-hashes-equal')

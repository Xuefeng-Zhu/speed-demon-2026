#!/usr/bin/env python3
"""sloc.py [--repo DIR] [--rev REV] [--json] [track|path/to/main.rs ...]

S = code lines of `rustfmt --edition 2021` output of main.rs (blank lines and lines starting with
// skipped, same as `grep -cvE '^\\s*$|^\\s*//'`) + Dockerfile line count (non-blank lines; board
matched 376+7=383 for D). Args: track letters (default a b c d) read from the working tree (or
--rev), or explicit main.rs paths (Dockerfile taken from ../Dockerfile if present)."""
import argparse, json, os, re, subprocess, sys, tempfile

REPO = '/projects/sandbox/speed-demon-2026'
PAT = re.compile(r'^\s*$|^\s*//')


def code_lines(src):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'main.rs')
        open(p, 'w').write(src)
        out = subprocess.run(['rustfmt', '--edition', '2021', '--emit', 'stdout', p],
                             capture_output=True, text=True, check=True).stdout
    # rustfmt --emit stdout prefixes a "<path>:\n\n" header; skip it
    lines = out.split('\n')
    if lines and lines[0].endswith(':') and lines[0].rstrip(':').endswith('main.rs'):
        lines = lines[1:]
    return sum(1 for l in lines if not PAT.match(l))


def dock_lines(txt):
    return sum(1 for l in txt.splitlines() if l.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', default=REPO)
    ap.add_argument('--rev')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('items', nargs='*', default=['a', 'b', 'c', 'd'])
    a = ap.parse_args()
    res = {}
    for it in a.items:
        if len(it) == 1:
            if a.rev:
                g = lambda f: subprocess.run(['git', '-C', a.repo, 'show', f'{a.rev}:track-{it}/{f}'],
                                             capture_output=True, text=True, check=True).stdout
                src, dock = g('src/main.rs'), g('Dockerfile')
            else:
                src = open(f'{a.repo}/track-{it}/src/main.rs').read()
                dock = open(f'{a.repo}/track-{it}/Dockerfile').read()
        else:
            src = open(it).read()
            dp = os.path.join(os.path.dirname(os.path.abspath(it)), '..', 'Dockerfile')
            dock = open(dp).read() if os.path.exists(dp) else ''
        c, d = code_lines(src), dock_lines(dock)
        res[it] = {'code': c, 'dockerfile': d, 'S': c + d}
        if not a.json:
            print(f'{it}: code {c} + Dockerfile {d} = S {c + d}')
    if a.json:
        print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()

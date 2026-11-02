#!/usr/bin/env python3
"""VM side: build Track B contexts with the official Dockerfile and run them like the board.

docker-ab.py ROUNDS name=context_dir [name=context_dir ...]
Builds each context with `docker build --network=none` after the official Dockerfile
check, then runs the images in interleaved random order with the flags of the
official harness/run_submission.py (cpuset 0-11, 8 GiB, read-only root, no network,
uid 65534 through sd-timer). Docker here uses the systemd cgroup driver, so each run
gets its own `kb-<id>.slice` parent and M is that slice's memory.peak. Inputs are
pre-warmed outside the run's cgroup. Every output is hash-checked.
"""
import hashlib, json, os, random, statistics, subprocess, sys, uuid

H = os.path.expanduser('~/kiro-b/harness')
sys.path.insert(0, H)
import dockerfile_check  # noqa: E402

K = os.path.expanduser('~/kiro-b')
DATA = f'{K}/data/s1'
EXPECTED = 'f86973c210228141bcb6f1f1b10188ad2a9b65f71e7cd7cf4590b38de4e80927'
TIMER = os.path.expanduser('~/kiro-b/timer/sd-timer')


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def build(name, ctx):
    allow = json.load(open(f'{H}/allowlist.json'))['images']
    problems = dockerfile_check.check(open(f'{ctx}/Dockerfile').read(), allow)
    if problems:
        sys.exit(f'{name}: Dockerfile check: {problems}')
    p = sh(['sudo', '-n', 'docker', 'build', '--network=none', '-t', f'kb-{name}', ctx])
    open(f'{K}/docker-build-{name}.log', 'w').write(p.stdout + p.stderr)
    if p.returncode:
        sys.exit(f'{name}: build failed, see docker-build-{name}.log\n{p.stderr[-3000:]}')
    size = int(sh(['sudo', '-n', 'docker', 'image', 'inspect', '-f', '{{.Size}}', f'kb-{name}']).stdout)
    print(f'built kb-{name}: image {size / 1e6:.1f} MB', flush=True)


def run(name):
    rid = uuid.uuid4().hex[:12]
    work = f'/dev/shm/kb-docker/{rid}'
    os.makedirs(f'{work}/out')
    os.makedirs(f'{work}/sd')
    os.chmod(f'{work}/out', 0o777)
    os.chmod(f'{work}/sd', 0o700)
    sh(['sudo', '-n', 'chown', 'root:root', f'{work}/sd'])
    slice_ = f'kb-{rid}.slice'
    cmd = ['sudo', '-n', 'docker', 'run', '--name', f'kb-{rid}', '--no-healthcheck', '--user=0:0',
           f'--cgroup-parent={slice_}', '--cpuset-cpus=0-11', '--cpuset-mems=0',
           '--memory=8g', '--memory-swap=8g', '--pids-limit=512', '--network=none', '--read-only',
           '--tmpfs', '/tmp:rw,size=1g,exec', '--cap-drop=ALL', '--cap-add=SETUID', '--cap-add=SETGID',
           '--security-opt=no-new-privileges', '--ulimit', 'nofile=8192:8192',
           '-v', f'{DATA}:/data:ro', '-v', f'{work}/out:/out:rw', '-v', f'{work}/sd:/sd',
           '-v', f'{os.path.dirname(TIMER)}:/sd-bin:ro', '-e', 'TRACK=b',
           '--entrypoint', '/sd-bin/sd-timer', f'kb-{name}', '/sd/timing.json', '65534', '65534', '--', '/app/solution']
    p = sh(cmd)
    if p.returncode:
        sys.exit(f'{name}: run failed {p.stderr[-2000:]}')
    peak = int(sh(['sudo', '-n', 'cat', f'/sys/fs/cgroup/kb.slice/{slice_}/memory.peak']).stdout.split()[0])
    timing = json.loads(sh(['sudo', '-n', 'cat', f'{work}/sd/timing.json']).stdout)
    diff = [l for l in sh(['sudo', '-n', 'docker', 'diff', f'kb-{rid}']).stdout.splitlines()
            if l.split(maxsplit=1)[-1] not in ('/data', '/out', '/sd', '/sd-bin', '/tmp')]
    sh(['sudo', '-n', 'docker', 'rm', '-fv', f'kb-{rid}'])
    sh(['sudo', '-n', 'systemctl', 'stop', slice_])
    h = hashlib.sha256(open(f'{work}/out/results.txt', 'rb').read()).hexdigest()
    sh(['sudo', '-n', 'rm', '-rf', work])
    if h != EXPECTED or timing['exit_code'] or diff:
        sys.exit(f'{name}: bad run hash={h} timing={timing} diff={diff}')
    return timing['wall_ns'] / 1e6, peak


def main():
    rounds = int(sys.argv[1])
    images = dict(a.split('=', 1) for a in sys.argv[2:])
    for name, ctx in images.items():
        build(name, ctx)
    for f in ('docs.txt', 'queries.txt'):  # pre-warm outside any run cgroup
        open(f'{DATA}/{f}', 'rb').read()
    names = list(images)
    res = {n: [] for n in names}
    for n in names:
        run(n)  # discard one warm-up run each
    for _ in range(rounds):
        random.shuffle(names)
        for n in names:
            res[n].append(run(n))
    base = [w for w, _ in res[list(images)[0]]]
    for n in images:
        walls = [w for w, _ in res[n]]
        peaks = [p for _, p in res[n]]
        pair = statistics.median(100 * (a / b - 1) for a, b in zip(walls, base))
        print(f'{n:8s} wall med {statistics.median(walls):7.1f} ms  min {min(walls):7.1f}  paired {pair:+6.2f}%  '
              f'M max {max(peaks) / 1e6:5.1f} MB  med {statistics.median(peaks) / 1e6:5.1f} MB')


main()

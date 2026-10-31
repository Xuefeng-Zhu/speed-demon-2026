#!/usr/bin/env python3
import collections
import datetime
import os
import random
import subprocess
import sys
import tempfile

binary = os.environ.get('INGEST_BINARY', '/tmp/speed-demon-a-ingest')
def check(seed, count):
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory() as d:
        data = os.path.join(d, 'requests.log')
        output = os.path.join(d, 'summary.txt')
        groups = collections.defaultdict(list)
        errors = collections.Counter()
        endpoints = ['/', '/v2/orders', '/v2/orders-export', '/v2/orders.csv', '/v2/orders/{id}', '/v2/ordersByDate', '/v2/orders_legacy', '/v2/orderstatus', '/x'+'a'*123] + ['/api/item/%s' % i for i in range(1842)]
        days = [datetime.datetime(2026,10,30,18) + datetime.timedelta(hours=i) for i in range(72)]
        methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
        with open(data, 'w') as f:
            last = ''
            for i in range(count):
                if i % 1717 == 0 and last:
                    line = last
                else:
                    dt = rng.choice(days) + datetime.timedelta(seconds=rng.randrange(3600), microseconds=rng.randrange(1000000))
                    endpoint = rng.choice(endpoints) if i % 4 == 0 else endpoints[int((rng.random() ** 4) * len(endpoints))]
                    status = rng.choice([100,200,299,399,400,499,500,501,599])
                    latency = rng.choice([0,4294967295]) if i % 31 == 0 else rng.randrange(200000)
                    line = dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ') + f' {rng.choice(methods)} {endpoint} {status} {latency}\n'
                f.write(line)
                ts, _, endpoint, status, latency = line.split()
                key = (ts[:13] + ':00:00Z', endpoint)
                groups[key].append(int(latency))
                errors[key] += int(status) >= 500
                last = line
        subprocess.run([binary, data, output], check=True)
        with open(output) as f:
            for key in sorted(groups):
                values = sorted(groups[key]); n = len(values); e = errors[key]
                vals = [values[(p*n+99)//100-1] for p in [50,95,99]]
                expected = f'{key[0]} {key[1]} {n} {vals[0]} {vals[1]} {vals[2]} {e} {e*1000000//n}\n'
                got = f.readline()
                if got != expected: raise AssertionError((got, expected))
            assert not f.read()
        print(f'PASS seed={seed}, records={count}, groups={len(groups)}')
for seed, count in [(0, 0), (1, 1000), (2, 100000), (999, 100000)]: check(seed, count)

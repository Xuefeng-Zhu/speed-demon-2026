#!/usr/bin/env python3
"""Screen open-address probe counts, not adversarial hash resistance."""
import itertools
import string

MASK64 = (1 << 64) - 1
alphabet = string.ascii_lowercase + string.digits
keys = [int.from_bytes(''.join(v).encode(), 'little')
        for length in (1, 2, 3) for v in itertools.product(alphabet, repeat=length)]


def old(x):
    x ^= x >> 30
    x = x * 0xbf58476d1ce4e5b9 & MASK64
    x ^= x >> 27
    x = x * 0x94d049bb133111eb & MASK64
    return (x ^ (x >> 31)) >> 32


def one(x):
    x ^= x >> 30
    x = x * 0xbf58476d1ce4e5b9 & MASK64
    x ^= x >> 27
    return (x ^ ((x << 21 | x >> 43) & MASK64)) >> 32


def simple(x):
    x ^= ((x >> 23) | (x << 41)) & MASK64
    return ((x * 0x9e3779b97f4a7c15) & MASK64) >> 32


for name, h in [('old', old), ('one', one), ('simple', simple)]:
    slots = [None] * 131072
    maximum = total = 0
    for key in keys:
        pos, extra = h(key) & (len(slots) - 1), 0
        while slots[pos] is not None:
            extra += 1
            pos = (pos + 1) & (len(slots) - 1)
        slots[pos] = key
        total += extra
        maximum = max(maximum, extra)
    print(name, 'keys', len(keys), 'total_extra_probes', total,
          'max_extra_probes', maximum)

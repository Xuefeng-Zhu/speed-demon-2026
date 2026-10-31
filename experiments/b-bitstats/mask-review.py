#!/usr/bin/env python3
"""Independently verify the six-popcount weighted bit-position identity."""
import random

MASKS = (0xAAAAAAAAAAAAAAAA, 0xCCCCCCCCCCCCCCCC, 0xF0F0F0F0F0F0F0F0,
         0xFF00FF00FF00FF00, 0xFFFF0000FFFF0000, 0xFFFFFFFF00000000)

def check(x):
    result = sum((x & mask).bit_count() << k for k, mask in enumerate(MASKS))
    expected = sum(i for i in range(64) if (x >> i) & 1)
    assert result == expected, (hex(x), result, expected)

for word in range(65536):
    check(word)
rng = random.Random(0x42535441)
for _ in range(200000):
    check(rng.getrandbits(64))
for word in (0, (1 << 64) - 1, 0x0101010101010101, 0x8080808080808080,
             0xAAAAAAAAAAAAAAAA, 0x5555555555555555):
    check(word)
print('PASS 65,536 low-16 masks, 200,000 random 64-bit masks and extremes')

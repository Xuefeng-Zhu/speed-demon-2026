#!/usr/bin/env python3
"""Enumerate SC schedules of the three atomic linearization points of three workers.

This models slot-load, compare/exchange, and fetch-or / serialized fallback.
The concrete Acquire/AcqRel publication argument is documented separately;
this is not a weak-memory model checker or a sanitizer.
"""
from itertools import product

schedules = 0

def explore(names, groups, stage, observed, slot, fast, fallback, counted):
    global schedules
    if all(x == 3 for x in stage):
        schedules += 1
        expected = set(zip(names, groups))
        assert counted == expected, (names, groups, counted, expected)
        assert len(fast | fallback) == len(expected)
        return
    for t, step in enumerate(stage):
        if step == 3:
            continue
        st=list(stage); obs=list(observed)
        if step == 0:
            obs[t] = slot
            st[t] = 1 if slot is None else 2
            explore(names, groups, tuple(st), tuple(obs), slot, fast, fallback, counted)
        elif step == 1:
            # CAS from null: either publish the name, or observe the winner.
            winner = names[t] if slot is None else slot
            obs[t] = winner
            st[t] = 2
            explore(names, groups, tuple(st), tuple(obs), winner, fast, fallback, counted)
        else:
            key=(names[t], groups[t]); st[t] = 3
            store = fast if obs[t] == names[t] else fallback
            new = key not in store
            if new:
                assert key not in counted, (names, groups, key, slot)
            explore(names, groups, tuple(st), tuple(obs), slot,
                    fast | {key} if store is fast else fast,
                    fallback | {key} if store is fallback else fallback,
                    counted | {key} if new else counted)

for names in product(('empty', 'escaped'), repeat=3):
    for groups in product((0, 64), repeat=3):
        explore(names, groups, (0,0,0), (None,None,None), None, set(), set(), set())
print(f'PASS: {schedules} SC schedules, three simultaneous names across group bit boundaries')

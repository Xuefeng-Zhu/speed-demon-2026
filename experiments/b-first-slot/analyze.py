#!/usr/bin/env python3
"""Summarize every saved adjacent pair; warmups are excluded, no rows trimmed."""
import argparse
import json
import random
import statistics
from pathlib import Path


def summarize(pairs, bootstrap):
    result = {'pairs': len(pairs)}
    for field in ('wall_s', 'cpu_s', 'cgroup_peak_bytes'):
        ratios = [p['variant'][field] / p['control'][field] for p in pairs]
        item = {'median_change_pct': 100 * (statistics.median(ratios) - 1),
                'wins': sum(r < 1 for r in ratios)}
        if bootstrap:
            rng = random.Random(5201)
            samples = sorted(statistics.median(rng.choices(ratios, k=len(ratios)))
                             for _ in range(20000))
            item['descriptive_bootstrap95_change_pct'] = [
                100 * (samples[i] - 1) for i in (499, 19499)]
        result[field] = item
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', nargs='?', type=Path,
                        default=Path(__file__).with_name('results.json'))
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    pairs = [p for p in data['pairs'] if not p['warmup']]
    assert len(data['pairs']) == 114 and len(pairs) == 108
    assert len({(p['phase'], p['dataset'], p['rep']) for p in data['pairs']}) == 114
    output = {}
    for dataset in ('seed1', 'seed2'):
        own = [p for p in pairs if p['dataset'] == dataset]
        assert len(own) == 54
        output[dataset] = {'all': summarize(own, True), 'rounds': {}}
        for phase, count in (('screen', 9), ('probe-confirm', 20), ('probe-confirm2', 25)):
            rows = [p for p in own if p['phase'] == phase]
            assert len(rows) == count
            output[dataset]['rounds'][phase] = summarize(rows, False)
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()

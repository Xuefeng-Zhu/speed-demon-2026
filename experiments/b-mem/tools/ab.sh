#!/bin/sh
# ab.sh <cand-bin> <pairs> <threads> <report-name> [baseline-bin]: paired run of
# experiments/b-linux-profile/run.py (hash asserted on every run, 1 warmup) and
# experiments/b-filter-parse/pair.py. Binaries are names in $D/bin (baseline default base-b7c4).
D=/projects/sandbox/.data; R=/projects/sandbox/speed-demon-2026
B=${5:-$D/bin/base-b7c4}
mkdir -p $D/mem/reports
python3 $R/experiments/b-linux-profile/run.py --binary $D/bin/$1 --baseline $B --data $D/speed-b-full --runs $2 --threads $3 --report $D/mem/reports/$4.json >/dev/null 2>$D/mem/reports/$4.err || { echo FAIL; tail $D/mem/reports/$4.err; }
python3 $R/experiments/b-filter-parse/pair.py $D/mem/reports/$4.json

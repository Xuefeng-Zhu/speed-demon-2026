#!/bin/sh
# ab.sh <cand-bin> <runs> <threads> <report-name> [baseline-bin]
D=/projects/sandbox/.data; R=/projects/sandbox/speed-demon-2026
B=${5:-$D/bin/lean-final}
python3 $R/experiments/b-linux-profile/run.py --binary $D/bin/$1 --baseline $B --data $D/speed-b-full --runs $2 --threads $3 --report $D/s3/$4.json >/dev/null 2>$D/s3/$4.err || { echo FAIL; tail $D/s3/$4.err; }
python3 $R/experiments/b-filter-parse/pair.py $D/s3/$4.json

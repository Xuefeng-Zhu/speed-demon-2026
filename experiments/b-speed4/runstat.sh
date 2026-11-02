#!/bin/bash
# runstat.sh bin [n]: run an instrumented binary n times on seed 1, print summed TSC stats (Mcyc).
cd ~/kiro-b
for r in $(seq ${2:-2}); do
SD_DATA=data/s1 SD_OUT=/dev/shm/kbs-$1 taskset -c 0-11 bin/$1 2>&1 | awk -v b=$1 '/scanstat/{a+=$2;p+=$3;c+=$4;d+=$5;e+=$6;next} /^parse/{pa=$2} /^start/{sa=$2} /^end/{en=$2} END {printf "%-12s parse %5.1f start %5.1f end %6.1f | pass1 %5d pass2 %5d cb %4d csr %4d answer %4d\n", b, pa, sa, en, a, p, c, d, e}'
done

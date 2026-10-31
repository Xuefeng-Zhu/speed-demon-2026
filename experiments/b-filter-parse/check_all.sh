#!/bin/sh
# Usage: [CHK_ROOT=dir] [CHK_TIMEOUT=s] check_all.sh <binary> [threads]
# Runs the Track B binary on every seed and edge fixture under $CHK_ROOT/seeds/*/ and
# $CHK_ROOT/edge/*/ (default CHK_ROOT=/projects/sandbox/.data; dirs with ref/results.txt)
# and compares results.txt byte for byte with the reference. Each run is wrapped in
# timeout $CHK_TIMEOUT (default 60 s) so a hang counts as a failure.
# XFAIL lists fixtures the dddc0ea baseline also fails (docs.txt without trailing LF,
# outside spec 2.1: panic in masks()). They are reported but do not fail the run;
# if one of them starts passing it is reported as XPASS.
B=${1:?binary}; T=${2:-}
XFAIL=${XFAIL-"edge/no_lf edge/no_lf_docs"}
R=${CHK_ROOT:-/projects/sandbox/.data}; TO=${CHK_TIMEOUT:-60}; O=$R/check-out; pass=0; fail=0; xfail=0
for d in $R/seeds/*/ $R/edge/*/; do
  d=${d%/}; [ -f "$d/ref/results.txt" ] || continue
  n=$(basename "$(dirname "$d")")/$(basename "$d"); o=$O/$n; rm -rf "$o"; mkdir -p "$o"
  if [ -n "$T" ]; then SD_THREADS=$T SD_DATA=$d SD_OUT=$o timeout "$TO" "$B" >"$o/log" 2>&1; else SD_DATA=$d SD_OUT=$o timeout "$TO" "$B" >"$o/log" 2>&1; fi
  rc=$?; ok=0; [ $rc -eq 0 ] && cmp -s "$o/results.txt" "$d/ref/results.txt" && ok=1
  case " $XFAIL " in
    *" $n "*) if [ $ok -eq 1 ]; then echo "XPASS $n"; pass=$((pass+1)); else xfail=$((xfail+1)); fi ;;
    *) if [ $ok -eq 1 ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL $n (exit $rc)"; fi ;;
  esac
done
echo "pass=$pass fail=$fail xfail=$xfail"; [ $fail -eq 0 ]

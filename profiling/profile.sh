#!/bin/bash
# Profile one benchmark version: flame graph, perf report and perf stat counters.
#
# usage: profiling/profile.sh <nbody|raytrace> <original|optimized>
#
# Outputs (results/profiling/<bench>/<version>/, or $PROFILE_OUT_DIR/<bench>/<version>/):
#   flamegraph.svg   flame graph generated with pyperformance (--hook perf_record)
#   perf_report.txt  perf report --stdio (call graph, symbols from python3-dbg)
#   stacks.folded    collapsed call stacks behind the flame graph (sample counts)
#   flamegraph_summary.txt  top frames and time by category, from stacks.folded
#   perf_stat.txt    hardware counters for a fixed amount of work
#
# Environment:
#   PROFILE_OUT_DIR  output root (default: results/profiling)
#   PROFILE_FAST=1   pyperformance --fast while recording (quick test)
#   STAT_ONLY=1      only redo the perf stat counters
#
# Notes:
# - Sampling uses python3-dbg so perf can resolve CPython's internal functions.
# - Sampling uses -e cpu-clock: in this QEMU VM the default 'cycles' event
#   records no samples in frequency mode (-F), while cpu-clock works.
# - Kernel frames show as [unknown]: this VM's kernel (linux-kvm) is built
#   without CONFIG_KALLSYMS and uses KASLR, so perf cannot name kernel
#   functions. Only the small kernel share of samples is affected.
# - perf.data is large and binary, so it is kept outside the repository.
set -euo pipefail

BENCH=$1
VERSION=$2
REPO=$(cd "$(dirname "$0")/.." && pwd)
FLAMEGRAPH=${FLAMEGRAPH:-$HOME/FlameGraph}
DATA=${PERF_DATA_DIR:-$HOME/perf-data}/$BENCH-$VERSION
OUT=${PROFILE_OUT_DIR:-$REPO/results/profiling}/$BENCH/$VERSION
FINAL_nbody=locals
FINAL_raytrace=combined
STAT_LOOPS_nbody=5
STAT_LOOPS_raytrace=5

final_var=FINAL_$BENCH
loops_var=STAT_LOOPS_$BENCH
if [ "$VERSION" = original ]; then
    MANIFEST_ARGS=()
    SCRIPT=$REPO/$BENCH/original/run_benchmark.py
else
    DIR=$REPO/$BENCH/optimized/${!final_var}
    MANIFEST_ARGS=(--manifest "$DIR/MANIFEST")
    SCRIPT=$DIR/bm_$BENCH/run_benchmark.py
fi

mkdir -p "$DATA" "$OUT"

if [ "${STAT_ONLY:-0}" != 1 ]; then
cd "$DATA"  # pyperformance creates its venv/ in the current directory

echo "== perf report (project guide: perf record -F 999 -g -- python3-dbg -m pyperformance run)"
perf record -e cpu-clock -F 999 -g -o "$DATA/perf.data" -- \
    python3-dbg -m pyperformance run ${PROFILE_FAST:+--fast} "${MANIFEST_ARGS[@]}" --bench "$BENCH" \
    > "$DATA/pyperformance.log" 2>&1
perf report -i "$DATA/perf.data" --stdio --comm python > "$OUT/perf_report.txt" 2>/dev/null

echo "== flame graph (pyperformance --hook perf_record)"
# pyperformance's perf_record hook attaches perf to every benchmark worker
# process and enables recording only while the timed benchmark code runs
# (no interpreter startup, imports or calibration). It writes one
# perf.data.<uuid> per worker; their stacks are merged into one flame graph.
HOOK_DIR=$DATA/hook
rm -rf "$HOOK_DIR" && mkdir -p "$HOOK_DIR"
PYPERF_PERF_RECORD_DATA_DIR=$HOOK_DIR \
PYPERF_PERF_RECORD_EXTRA_OPTS="-e cpu-clock -F 999 -g" \
    python3-dbg -m pyperformance run ${PROFILE_FAST:+--fast} "${MANIFEST_ARGS[@]}" --bench "$BENCH" \
    --hook perf_record --inherit-environ PYPERF_PERF_RECORD_DATA_DIR,PYPERF_PERF_RECORD_EXTRA_OPTS \
    > "$DATA/pyperformance_hook.log" 2>&1
for f in "$HOOK_DIR"/perf.data.*; do
    perf script -i "$f" 2>/dev/null
done | "$FLAMEGRAPH/stackcollapse-perf.pl" > "$OUT/stacks.folded"
"$FLAMEGRAPH/flamegraph.pl" --title "$BENCH ($VERSION) - pyperformance --hook perf_record" \
    "$OUT/stacks.folded" > "$OUT/flamegraph.svg"
python3 "$REPO/profiling/summarize_flamegraph.py" "$OUT/stacks.folded" > "$OUT/flamegraph_summary.txt"

fi

echo "== perf stat (release python3, ${!loops_var} fixed loops, 5 repeats)"
# Two groups of events: with all 6 events at once, 'cycles' reads 0 in this VM
# (the virtual PMU has too few hardware counters for them together).
perf stat -r 5 -e cycles,instructions,branches,branch-misses \
    -o "$OUT/perf_stat.txt" -- \
    python3 "$REPO/profiling/workload.py" "$BENCH" "$SCRIPT" "${!loops_var}"
perf stat -r 5 -e cache-references,cache-misses,page-faults \
    -o "$OUT/perf_stat.txt" --append -- \
    python3 "$REPO/profiling/workload.py" "$BENCH" "$SCRIPT" "${!loops_var}"

echo "== done: $OUT"

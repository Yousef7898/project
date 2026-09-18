#!/bin/bash
# Python-level flame graph with py-spy.
#
# usage: profiling/pyspy_profile.sh <nbody|raytrace> <original|optimized>
#
# Why in addition to the perf/pyperformance flame graphs:
# perf samples the interpreter's C functions, and CPython 3.10 is built
# without frame pointers, so those flame graphs show what kind of work the
# interpreter does (dispatch, list indexing, dictionary lookups) but not which
# Python function or line it happens in. py-spy samples Python's own frames,
# so its flame graph carries Python function names and line numbers.
#
# Outputs (results/profiling/<bench>/<version>/, or $PROFILE_OUT_DIR/...):
#   pyspy_flamegraph.svg  Python-level flame graph (function names, call tree)
#   pyspy_stacks.folded   raw py-spy stacks (whole process, with line numbers)
#   pyspy_benchmark.folded  stacks inside the benchmark function only (flame graph input)
#   pyspy_top.txt         hottest Python lines and functions (self time)
set -euo pipefail

BENCH=$1
VERSION=$2
REPO=$(cd "$(dirname "$0")/.." && pwd)
FLAMEGRAPH=${FLAMEGRAPH:-$HOME/FlameGraph}
OUT=${PROFILE_OUT_DIR:-$REPO/results/profiling}/$BENCH/$VERSION
RATE=${PYSPY_RATE:-500}                     # samples per second
LOOPS_nbody=${PYSPY_LOOPS_NBODY:-30}           # ~7 s of work -> several thousand samples
LOOPS_raytrace=${PYSPY_LOOPS_RAYTRACE:-8}

FINAL_nbody=locals
FINAL_raytrace=combined
final_var=FINAL_$BENCH
loops_var=LOOPS_$BENCH

if [ "$VERSION" = original ]; then
    SCRIPT=$REPO/$BENCH/original/run_benchmark.py
else
    SCRIPT=$REPO/$BENCH/optimized/${!final_var}/bm_$BENCH/run_benchmark.py
fi

mkdir -p "$OUT"

echo "== py-spy: $BENCH $VERSION (${!loops_var} loops at $RATE Hz)"
# Start the workload, then attach py-spy to it. (Letting py-spy spawn the
# process itself intermittently fails with "No child process" on this VM.)
python3 "$REPO/profiling/workload.py" "$BENCH" "$SCRIPT" "${!loops_var}" &
WORKLOAD_PID=$!
py-spy record --rate "$RATE" --format raw --pid "$WORKLOAD_PID" \
    --output "$OUT/pyspy_stacks.folded" > /dev/null
wait "$WORKLOAD_PID"

# Flame graph of the benchmark function only (no startup/imports), frames per
# function, top box = the source line being executed.
python3 "$REPO/profiling/pyspy_fold.py" "$OUT/pyspy_stacks.folded" "$SCRIPT" \
    > "$OUT/pyspy_benchmark.folded"
"$FLAMEGRAPH/flamegraph.pl" \
    --title "$BENCH ($VERSION): Python-level flame graph (py-spy, $RATE Hz)" \
    --subtitle "width = share of run time, height = call stack, top box = source line" \
    --countname samples "$OUT/pyspy_benchmark.folded" > "$OUT/pyspy_flamegraph.svg"

python3 "$REPO/profiling/summarize_pyspy.py" "$OUT/pyspy_stacks.folded" > "$OUT/pyspy_top.txt"
echo "== done: $OUT/pyspy_flamegraph.svg"

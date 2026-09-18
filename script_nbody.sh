#!/bin/bash
# nbody: full pipeline for the HW/SW co-design project.
#
#   1. environment setup and dependency installation
#   2. correctness check (optimized versions compute the same results)
#   3. profiling of the original and optimized code:
#      flame graphs (pyperformance/perf and py-spy), perf report,
#      perf stat counters
#   4. benchmark execution with pyperformance: original and optimized
#   5. performance comparison
#
# usage:  sudo ./script_nbody.sh
#
# Environment variables:
#   SKIP_SETUP=1     skip step 1 (dependencies already installed)
#   ALL_VARIANTS=1   also benchmark every single optimization (locals, sqrt,
#                    both), not only the final one
#   FAST=1           quick run: pyperformance --fast instead of --rigorous
#                    (for testing the script, not for reported numbers)
#   OUT=<dir>        output directory (default: results/runs/nbody-<date>)
#
# The final optimized version is nbody/optimized/locals: positions and
# velocities are copied into local variables for the whole advance() call
# and written back to the lists once at the end.
set -euo pipefail

BENCH=nbody
FINAL=locals
VARIANTS=(locals sqrt both)

REPO=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:-$REPO/results/runs/$BENCH-$(date +%Y%m%d-%H%M%S)}
if [ "${FAST:-0}" = 1 ]; then MODE=--fast; else MODE=--rigorous; fi
WORK=${WORK:-$HOME/pyperf-work}   # pyperformance creates its venv/ here

if [ "$(id -u)" != 0 ]; then
    echo "run as root (perf and 'pyperf system tune' need it): sudo $0" >&2
    exit 1
fi

step() { echo; echo "========== $* =========="; }
run() { echo "\$ $*" | tee -a "$OUT/commands.log"; "$@"; }

mkdir -p "$OUT" "$WORK"
: > "$OUT/commands.log"

# ---------------------------------------------------------------------------
step "1. environment setup"
if [ "${SKIP_SETUP:-0}" != 1 ]; then
    run apt-get update
    # perf, debug build of Python (for symbols in perf), git
    run apt-get install -y linux-tools-common "linux-tools-$(uname -r)" python3-dbg python3-pip git
    run python3 -m pip install "pyperformance==1.14.0" py-spy
    # Brendan Gregg's FlameGraph scripts: render the stacks that pyperformance
    # records with --hook perf_record into flame graph SVGs
    if [ ! -d "$HOME/FlameGraph" ]; then
        run git clone --depth 1 https://github.com/brendangregg/FlameGraph "$HOME/FlameGraph"
    fi
fi
run perf --version
run python3-dbg --version
run python3 -m pyperformance --version

# ---------------------------------------------------------------------------
step "2. correctness check"
run python3 "$REPO/nbody/verify_nbody.py" | tee "$OUT/verify.txt"

# ---------------------------------------------------------------------------
# Profiling runs before 'pyperf system tune', which limits perf's sample rate.
step "3. profiling: flame graph, perf report, perf stat"
for version in original optimized; do
    # interpreter level: flame graph from pyperformance, perf report, counters
    run env PROFILE_OUT_DIR="$OUT/profiling" ${FAST:+PROFILE_FAST=1} \
        "$REPO/profiling/profile.sh" "$BENCH" "$version"
    # Python level: flame graph with function names and line numbers
    run env PROFILE_OUT_DIR="$OUT/profiling" \
        "$REPO/profiling/pyspy_profile.sh" "$BENCH" "$version"
done

# ---------------------------------------------------------------------------
step "4. benchmarks (pyperformance $MODE)"
cd "$WORK"
# Reduce system noise: pin to the benchmark CPU, move IRQs away, etc.
# (Turbo Boost cannot be changed inside the VM; that error is expected.)
run python3 -m pyperf system tune || true

run python3 -m pyperformance run "$MODE" -b "$BENCH" -o "$OUT/${BENCH}_original.json"
if [ "${ALL_VARIANTS:-0}" = 1 ]; then TO_RUN=("${VARIANTS[@]}"); else TO_RUN=("$FINAL"); fi
for v in "${TO_RUN[@]}"; do
    run python3 -m pyperformance run "$MODE" --manifest "$REPO/$BENCH/optimized/$v/MANIFEST" \
        -b "$BENCH" -o "$OUT/${BENCH}_$v.json"
done

# Undo the tuning (restores perf's maximum sample rate).
run python3 -m pyperf system reset || true

# ---------------------------------------------------------------------------
step "5. performance comparison"
files=("$OUT/${BENCH}_original.json")
for v in "${TO_RUN[@]}"; do files+=("$OUT/${BENCH}_$v.json"); done
run python3 -m pyperf compare_to --table "${files[@]}" | tee "$OUT/comparison.txt"
for f in "${files[@]}"; do
    run python3 -m pyperf stats "$f" >> "$OUT/stats.txt"
    run python3 -m pyperf hist "$f" >> "$OUT/histograms.txt"
done

echo
echo "done, results in: $OUT"

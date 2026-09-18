#!/bin/bash
# Build and run every test of the nbody accelerator.
#
#   1. floating-point operators vs Python (IEEE-754), bit for bit
#   2. full accelerator through its MMIO registers vs the golden model
#      (benchmark scene + 2, 3 and 16 bodies), bit for bit, with cycle counts
#   3. host driver: software fallback and offload through the register model
#
# usage: hw/nbody_accel/run_tests.sh
#   FP_VECTORS=<n>     random operator cases (default 20000)
#   BENCH_STEPS=<n>    time steps for the benchmark-scene system test (default 200)
# requires: iverilog (apt install iverilog), python3
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=${BUILD:-$HERE/build}
mkdir -p "$BUILD"
cd "$HERE"

echo "== 1. floating-point operators"
python3 model/gen_fp_vectors.py "${FP_VECTORS:-20000}"
iverilog -g2012 -I rtl -o "$BUILD/tb_fp_units.vvp" tb/tb_fp_units.v \
    rtl/fp_pipe.v rtl/fp_add.v rtl/fp_mul.v rtl/fp_div.v rtl/fp_sqrt.v
(cd tb && vvp -n "$BUILD/tb_fp_units.vvp" | grep -v readmemh) | tee "$BUILD/fp_units.log"
grep -q "^PASS" "$BUILD/fp_units.log"

echo "== 2. accelerator system test"
python3 model/nbody_golden.py "${BENCH_STEPS:-200}"
iverilog -g2012 -I rtl -o "$BUILD/tb_nbody_accel.vvp" tb/tb_nbody_accel.v rtl/*.v
: > "$BUILD/system.log"
for v in benchmark n2 n3 n16; do
    (cd tb && vvp -n "$BUILD/tb_nbody_accel.vvp" +vec=vectors/sys_$v.hex | grep -v readmemh) \
        | tee -a "$BUILD/system.log"
done
[ "$(grep -c '^PASS' "$BUILD/system.log")" = 4 ]

echo "== 3. host driver"
python3 sw/test_driver.py 1000 | tee "$BUILD/driver.log"
grep -q "^PASS" "$BUILD/driver.log"

echo
echo "all accelerator tests passed (logs in $BUILD)"

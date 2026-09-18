"""Speedup estimate for the nbody accelerator.

Inputs (all measured, nothing guessed except the stated assumptions):
- software time per benchmark iteration: pyperformance --rigorous medians in
  results/ (original and final optimized "locals" version, same session)
- hardware clock cycles per time step: from the RTL system simulation
  (tb_nbody_accel.v), which fits cycles = 6*P + 11*N + 84 exactly for
  N = 2, 3, 5, 16 (P = N(N-1)/2 pairs)

Assumptions (stated in the report):
- clock 100 MHz (10 ns) as specified in docs/design.md
- host overhead per advance() call: 70 MMIO register operations
  (measured with the driver) at MMIO_US each, plus one poll interval
- report_energy() stays in software (2 calls per iteration, 10 pairs each)

usage: python3 estimate_speedup.py
"""
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

CLOCK_HZ = 100e6
STEPS = 20000                 # advance(0.01, 20000) per benchmark iteration
N = 5
MMIO_OPS = 70
MMIO_US = 10.0                # pessimistic cost of one PCIe MMIO register access
POLL_US = 500.0               # driver poll interval (worst case wait)


def median_ms(path):
    with open(path) as f:
        data = json.load(f)
    values = []
    for run in data["benchmarks"][0]["runs"]:
        values.extend(run.get("values", []))
    return statistics.median(values) * 1e3


def cycles_per_step(n):
    p = n * (n - 1) // 2
    return 6 * p + 11 * n + 84


def main():
    sw_orig = median_ms(os.path.join(REPO, "results", "nbody_r2_original.json"))
    sw_opt = median_ms(os.path.join(REPO, "results", "nbody_r2_locals.json"))

    cyc = cycles_per_step(N)
    hw_step_us = cyc / CLOCK_HZ * 1e6
    hw_compute_ms = STEPS * hw_step_us / 1e3
    overhead_ms = (MMIO_OPS * MMIO_US + POLL_US) / 1e3
    # report_energy in software: ~ one tenth of a step of software work each, x2
    energy_ms = 2 * (sw_opt / STEPS)
    hw_total_ms = hw_compute_ms + overhead_ms + energy_ms

    print("Measured software (pyperformance --rigorous median, one iteration = "
          f"advance(0.01, {STEPS}) + 2 x report_energy)")
    print(f"  original            {sw_orig:8.1f} ms   {sw_orig / STEPS * 1e3:6.2f} us/step")
    print(f"  optimized (locals)  {sw_opt:8.1f} ms   {sw_opt / STEPS * 1e3:6.2f} us/step")
    print()
    print(f"Accelerator (N={N}, {N * (N - 1) // 2} pairs, {CLOCK_HZ / 1e6:.0f} MHz)")
    print(f"  cycles per step (RTL simulation)   {cyc}")
    print(f"  time per step                      {hw_step_us:.2f} us")
    print(f"  {STEPS} steps                         {hw_compute_ms:.1f} ms")
    print(f"  host overhead ({MMIO_OPS} MMIO x {MMIO_US:.0f} us + poll)  {overhead_ms:.2f} ms")
    print(f"  report_energy in software          {energy_ms:.3f} ms")
    print(f"  total per iteration                {hw_total_ms:.1f} ms")
    print()
    print(f"Estimated speedup vs original software:   {sw_orig / hw_total_ms:.1f}x")
    print(f"Estimated speedup vs optimized software:  {sw_opt / hw_total_ms:.1f}x")
    print(f"Offloaded fraction of the iteration:      "
          f"{hw_compute_ms / hw_total_ms * 100:.1f}% of accelerated time")
    print()
    print("Scaling with the number of bodies (software cost per step grows with P too)")
    sw_pair_us = (sw_opt / STEPS * 1e3) / (N * (N - 1) / 2 + N)   # rough: per pair+body unit
    print("   N   pairs  HW cycles  HW us/step  SW(opt) us/step (scaled)  speedup")
    for n in (2, 5, 8, 16):
        p = n * (n - 1) // 2
        c = cycles_per_step(n)
        hw = c / CLOCK_HZ * 1e6
        sw = sw_pair_us * (p + n)
        print(f"  {n:2d}  {p:5d}  {c:9d}  {hw:10.2f}  {sw:24.2f}  {sw / hw:6.1f}x")


if __name__ == "__main__":
    main()

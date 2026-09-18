# nbody accelerator: justification and performance estimate

## 1. Why advance() is a good candidate for acceleration

- **It is the whole benchmark.** One iteration is `report_energy()`,
  `advance(0.01, 20000)`, `report_energy()`; advance is essentially all of it.
  Amdahl's law is on our side: almost nothing is left on the CPU.
- **The cost is Python overhead, not math** (flame graph of the original,
  `results/profiling/nbody/original/analysis.txt`): interpreter dispatch 44.9%,
  float objects created/freed 12.9%, list indexing 14.8%, float arithmetic
  dispatch 19.4%. The actual floating-point operations are a tiny part of that
  and are exactly what dedicated hardware does in a few pipeline stages.
- **Fixed, regular, small dataflow.** Every step does the same N(N-1)/2 pair
  computations with no data-dependent control flow: a natural pipeline
  (the systolic/pipeline accelerator pattern).
- **Tiny state, no bulk data movement.** 7 doubles per body: 280 bytes for the
  benchmark. One transfer in, one out, per `advance()` call, independent of the
  number of steps. PCIe latency is paid once, not per step.
- **Pairs are independent within a step** (forces depend only on positions),
  so pairs stream through the pipeline back to back.

## 2. Performance estimate

From `model/estimate_speedup.py` (software: pyperformance --rigorous medians;
hardware: RTL simulation cycle counts):

| | per iteration | per step |
|---|---|---|
| software, original | 232.2 ms | 11.61 µs |
| software, optimized (locals) | 143.7 ms | 7.19 µs |
| accelerator compute (199 cycles × 10 ns) | 39.8 ms | 1.99 µs |
| + host overhead (70 MMIO ops × 10 µs + 0.5 ms poll) | 1.2 ms | |
| **accelerator total** | **41.0 ms** | |

**Estimated speedup: 5.7× vs the original, 3.5× vs our optimized software.**

Cycle count per time step, measured in simulation for N = 2, 3, 5 and 16
bodies, fits exactly:

    cycles = 6·P + 11·N + 84        (P = N(N-1)/2)

- 84: pipeline latency (81) + feed/drain control
- 6 per pair: velocity accumulation (launch + 3-cycle adders + write + control)
- 11 per body: position update (4-cycle multipliers + 3-cycle adders + control)

Because software cost also grows with P, the advantage grows with N:
estimated 1.3× at N = 2, 3.6× at N = 5, 5.1× at N = 8, 6.6× at N = 16
(vs optimized software).

Assumptions:
- 100 MHz clock is met with the stated operator latencies (not synthesized).
- MMIO register access 10 µs each (pessimistic; a user-space mmap'ed BAR is
  usually well below that).
- Offload used when `NUM_STEPS` is large; for a handful of steps the fixed
  1.2 ms host overhead dominates and the driver should stay in software.

## 3. How to reproduce the estimate
```
python3 hw/nbody_accel/model/estimate_speedup.py
```
It reads the pyperformance results (`results/nbody_r2_original.json`,
`results/nbody_r2_locals.json`) and uses the cycle formula measured by
`hw/nbody_accel/run_tests.sh`. Change `MMIO_US`, `POLL_US` or `CLOCK_HZ` at
the top of the script to see how the assumptions move the result.

## 4. Break-even: when offloading pays off
The host overhead (~1.2 ms per call) is paid once per `advance()` call, the
computation per step. Offloading wins when

    n_steps x (software time per step - accelerator time per step) > overhead

- vs original software: 1.2 ms / (11.61 - 1.99) us = about 125 steps
- vs optimized software: 1.2 ms / (7.19 - 1.99) us = about 230 steps

The benchmark calls `advance(0.01, 20000)`: far above break-even. For short
calls the driver should stay in software (see `sw/nbody_accel_driver.py`).

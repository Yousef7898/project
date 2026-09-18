# nbody accelerator: area estimate and design trade-offs

Justification and performance estimate: `performance.md`.

## 1. Area estimate (rough, not synthesized)

| Resource | Count | Estimate |
|---|---|---|
| fp_add | 14 (5 pipeline, 6 accumulator, 3 position) | ~1.5k LUTs each (align shifter, LZC, normalize shifter, round) |
| fp_mul | 15 (12 pipeline, 3 position) | ~8 DSP blocks + ~0.3k LUTs each (53×53 product) |
| fp_div, fp_sqrt | 1 each | ~56 × 58-bit subtract/compare stages, ~3–4k LUTs + ~3k FF each |
| body state | 7 × 16 × 64 bits | 7.2 kbit (registers) |
| pair result buffer | 6 × 120 × 64 bits | 46 kbit (block RAM) |
| delay lines | dx,dy,dz (74 deep), masses (73), d2 (28), tag | ~25 kbit (shift-register LUTs / BRAM) |
| **total** | | **~35k LUTs, ~120 DSP, ~40–60k FF, a few BRAMs** |

This fits a mid-range FPGA (for example a device with ~200k LUTs and several
hundred DSP blocks) with plenty of room.

## 2. Trade-offs

Our analysis of the design choices, with the numbers behind each one.

### 2.1 Number format: IEEE double vs fixed point
| | IEEE-754 double (chosen) | 64-bit fixed point |
|---|---|---|
| results | stay exactly like the software (bit-identical with the sqrt formula) | drift from the software, the error grows over many steps (20000 per call) |
| logic | alignment, normalization and rounding in every add/mul | plain adders and DSP multipliers |
| area | ~35k LUTs | smaller: roughly half the LUTs, same DSPs |
| power | higher | lower |

We chose IEEE double because the results stay exactly like the software.

### 2.2 Pipeline depth vs operating frequency (div and sqrt)
Div and sqrt compute 56 result bits; the question is how many bits per
pipeline stage.

| bits per stage | stages | clock | cycles per step | time per step | cost |
|---|---|---|---|---|---|
| 1 | 56 | ~150 MHz | 255 | ~1.70 µs | ~2x the pipeline registers, more power |
| **2 (chosen)** | **28** | **100 MHz** | **199** | **1.99 µs** | **balance** |
| 4 | 14 | ~50 MHz | 171 | ~3.4 µs | fewer registers, but the clock drops a lot |

2 bits per stage at 100 MHz is our balance. (The 150 MHz option also assumes
add and mul keep their stage counts at that clock.)

### 2.3 Accumulation order
The velocity updates have to be applied in pair order to keep the results
exact: floating-point addition is not associative, and a body appears in
several pairs, so a different order gives slightly different results.

### 2.4 Parallelism vs area
- **Position update in parallel for all bodies**: saves about 20% of the
  cycles per step (~44 of 199 for 5 bodies) but costs 5x the area of that
  block (5 sets of 3 multipliers + 3 adders instead of 1).
- **A second pair_force pipeline** does not help much: it only halves the
  feed phase (P = 10 cycles per step), while the 81-cycle pipeline latency
  stays. Latency is the problem here, not throughput.

### 2.5 Interface: MMIO vs DMA
- Small systems (up to 16 bodies, 280 bytes of state for the benchmark):
  MMIO registers, 70 register operations per call, simple and no buffer
  management.
- Big systems: DMA would be better, one transfer of a host buffer
  (7 x 8 bytes per body) instead of per-register accesses, at the cost of
  bus-master logic in the card and IOMMU setup in the driver.

### 2.6 When the card pays off
The PCIe cost (~1.2 ms per call, see `performance.md`) is fixed per call, so
the card only pays off when there are many steps per call: above ~125 steps
vs the original software, ~230 vs the optimized one. The benchmark does
20000 steps per call.

### 2.7 Power and energy
- The CPU core is busy for the whole software run (232 ms per iteration for
  the original code).
- The card finishes about 5x faster (41 ms), and the CPU core can idle while
  it waits, so the energy per run should drop, even though the FPGA adds its
  own power.
- Assumption: the FPGA is already configured and ready. Loading the FPGA
  design (bitstream) takes tens of milliseconds to seconds; if it had to be
  done for every call it would cost about as much as the software run itself
  and the benefit would disappear. As with a GPU, the card is configured once
  (at boot or program start) and stays ready, drawing some idle power between
  calls.

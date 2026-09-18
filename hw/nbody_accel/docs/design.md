# nbody force accelerator: architecture specification

Hardware accelerator for the `advance()` loop of the pyperformance **nbody**
benchmark: pairwise gravitational forces, velocity updates and position
updates, for many time steps, with no software involvement between steps.

## 1. Why this component

Profiling (see `results/profiling/nbody/`) shows that essentially all of the
benchmark's run time is spent in `advance()`, and that the cost is interpreter
overhead around very simple floating-point math, not the math itself:

| Flame graph category (original, self time) | Share |
|---|---|
| interpreter loop (bytecode dispatch)        | 44.9% |
| float arithmetic (`binary_op1`, `float_mul`, ...) | 19.4% |
| list indexing (`list_ass_item`, `PyNumber_AsSsize_t`, ...) | 14.8% |
| float objects create/free (`PyFloat_FromDouble`, `float_dealloc`) | 12.9% |
| math library (`pow`)                        | 1.8% |

A Python float operation costs tens of nanoseconds (bytecode dispatch, type
checks, a heap-allocated result object). In hardware the same operation is a
few pipeline stages with no allocation, no dispatch and no type checks. The
per-step work is small and fixed (N(N-1)/2 pairs), the data fits in on-chip
registers, and steps only need the previous step's state, so the whole loop
can run on the device with a single transfer in and out.

## 2. What the hardware computes

Exactly the software algorithm, in the same operation order, in IEEE-754
double precision (the format of Python `float`):

```
for step in 0 .. NUM_STEPS-1:
    for each pair (i, j), i < j, in order (0,1), (0,2), ..., (N-2, N-1):
        dx = x[i] - x[j];  dy = y[i] - y[j];  dz = z[i] - z[j]
        d2  = (dx*dx + dy*dy) + dz*dz
        mag = dt / (d2 * sqrt(d2))            # software: dt * d2 ** (-1.5)
        b1m = m[i] * mag;  b2m = m[j] * mag
        vx[i] -= dx * b2m;  vy[i] -= dy * b2m;  vz[i] -= dz * b2m
        vx[j] += dx * b1m;  vy[j] += dy * b1m;  vz[j] += dz * b1m
    for each body b:
        x[b] += dt * vx[b];  y[b] += dt * vy[b];  z[b] += dt * vz[b]
```

`d2 ** (-1.5)` and `1 / (d2 * sqrt(d2))` are mathematically identical.
Hardware uses the second form because +, -, x, / and sqrt are exactly
defined by IEEE-754 (one correctly rounded result), while `pow` is not.
The hardware result is therefore **bit-identical** to the software with the
sqrt formula (`nbody/optimized/sqrt`), and differs from the original `**`
version only by rounding (1.3e-9 relative after 20000 steps, measured).

## 3. System integration (block diagram)

```
 HOST (CPU)                                   ACCELERATOR CARD (FPGA, PCIe endpoint)
+---------------------------+                +----------------------------------------------------+
| Python benchmark          |                |  nbody_accel_top                                   |
|   advance(dt, n, bodies)  |                |                                                    |
|        |                  |                |  +-------------+      +-------------------------+  |
|        v                  |                |  | registers   |      | controller (FSM)        |  |
| nbody_accel_driver.py     |   PCIe link    |  | CTRL/STATUS |----->| step / pair / body      |  |
|  - device present?        |<==============>|  | NUM_BODIES  |      | counters                |  |
|    no  -> software advance|   BAR0 (MMIO)  |  | NUM_STEPS   |<-----| STEPS_DONE, DONE        |  |
|    yes -> write state,    |                |  | DT          |      +-----------+-------------+  |
|           start, poll,    |                |  | body state  |<----------+     | select i,j / b |
|           read state      |                |  | x..vz, m    |  read/write     v                |
|        |                  |                |  | (N <= 16)   |      +-------------------------+  |
|        v                  |                |  +-------------+----->| pair_force pipeline     |  |
| OS: PCIe driver / UIO,    |                |                       | sub,sq,add,sqrt,mul,div |  |
|     mmap of BAR0          |                |                       | -> 6 velocity deltas    |  |
+---------------------------+                |                       +-----------+-------------+  |
                                             |                                   v                |
                                             |  +-------------+      +-------------------------+  |
                                             |  | pair result |<-----| result buffer (per pair)|  |
                                             |  | accumulator |      +-------------------------+  |
                                             |  | 6x fp_add   |---> velocities                   |
                                             |  +-------------+                                   |
                                             |  | position    |---> positions                    |
                                             |  | update      |     (3x fp_mul, 3x fp_add)       |
                                             |  +-------------+                                   |
                                             +----------------------------------------------------+
```

## 4. Interfaces

### 4.1 Clock and reset
| Signal | Width | Direction | Meaning |
|---|---|---|---|
| `clk`   | 1 | in | system clock, target **100 MHz** (10 ns period) |
| `rst_n` | 1 | in | synchronous active-low reset |

### 4.2 MMIO bus (host view of BAR0)
Simple synchronous register bus, as exposed by a PCIe endpoint bridge (the
bridge itself is standard vendor IP and outside this design). 64-bit data so
one register holds one double.

| Signal | Width | Direction | Meaning |
|---|---|---|---|
| `mmio_addr`  | 16 | in  | register address (byte offset in BAR0) |
| `mmio_wen`   | 1  | in  | write strobe (1 cycle) |
| `mmio_wdata` | 64 | in  | write data |
| `mmio_ren`   | 1  | in  | read strobe (1 cycle) |
| `mmio_rdata` | 64 | out | read data, valid the cycle after `mmio_ren` |
| `irq_done`   | 1  | out | level interrupt: run finished (optional; driver may poll) |

### 4.3 Register map (BAR0)
| Offset | Name | Access | Width | Description |
|---|---|---|---|---|
| 0x0000 | `ID`         | R  | 64 | constant `0x4E424F4459414343` ("NBODYACC") |
| 0x0008 | `CTRL`       | W  | 64 | bit0 `START`: begin a run (ignored while busy) |
| 0x0010 | `STATUS`     | R  | 64 | bit0 `BUSY`, bit1 `DONE` (cleared by `START`) |
| 0x0018 | `NUM_BODIES` | RW | 64 | N, 2..16 |
| 0x0020 | `NUM_STEPS`  | RW | 64 | number of time steps (32 bits used) |
| 0x0028 | `DT`         | RW | 64 | time step, IEEE-754 double |
| 0x0030 | `STEPS_DONE` | R  | 64 | progress counter |
| 0x0038 | `CYCLES`     | R  | 64 | clock cycles of the last run (performance counter) |
| 0x1000 + 0x40*b + 8*f | `BODY[b].field[f]` | RW | 64 | f: 0 x, 1 y, 2 z, 3 vx, 4 vy, 5 vz, 6 m |

Body registers are written by the host only while not busy.

### 4.4 Internal floating-point operator interface
All operators are fixed-latency pipelines without back-pressure:

| Signal | Width | Meaning |
|---|---|---|
| `in_valid`  | 1  | input sample valid |
| `a`, `b`    | 64 | IEEE-754 doubles (`fp_sqrt` has only `a`) |
| `sub`       | 1  | `fp_add` only: 1 = a - b |
| `out_valid` | 1  | `in_valid` delayed by the operator latency |
| `y`         | 64 | result |

| Operator | Latency (cycles) at 100 MHz | Algorithm |
|---|---|---|
| `fp_add`  | 3  | align, add/subtract 56-bit mantissas, leading-zero count, normalize, round |
| `fp_mul`  | 4  | 53x53 significand product (DSP blocks), normalize, round |
| `fp_div`  | 28 | restoring digit recurrence, 2 quotient bits per stage |
| `fp_sqrt` | 28 | restoring digit recurrence, 2 root bits per stage |

Rounding: round to nearest, ties to even (IEEE default, what Python uses).
Supported values: zero and normal numbers (everything this workload
produces). NaN, infinity and subnormals are out of scope and documented as
such.

The RTL describes each operator as its arithmetic followed by `LATENCY`
register stages; synthesis retiming distributes those registers through the
logic. The latencies are assumptions for a mid-range FPGA at 100 MHz.

## 5. Architecture

RTL files (`hw/nbody_accel/rtl/`):

| File | Contents |
|---|---|
| `nbody_accel_top.v` | register block (MMIO decode, register map), body state memory, controller FSM, accumulator and position-update units |
| `pair_force.v` | the pair force pipeline (5.1) |
| `fp_add.v`, `fp_mul.v`, `fp_div.v`, `fp_sqrt.v` | IEEE-754 double operators |
| `fp_common.vh`, `fp_pipe.v`, `delay_line.v` | rounding/packing helper, fixed-latency output pipeline, shift-register delay line |


### 5.1 pair_force pipeline
Computes the six velocity deltas of one pair from positions and masses only
(positions do not change during the pair phase, so pairs are independent and
can be streamed through the pipeline back to back, one per clock cycle).

| Stage | Operation | Units | Latency |
|---|---|---|---|
| S1 | dx, dy, dz = pos_i - pos_j | 3x fp_add(sub) | 3 |
| S2 | dx², dy², dz² | 3x fp_mul | 4 |
| S3 | s = dx² + dy² | fp_add | 3 |
| S4 | d2 = s + dz² | fp_add | 3 |
| S5 | r = sqrt(d2) | fp_sqrt | 28 |
| S6 | den = d2 · r | fp_mul | 4 |
| S7 | mag = dt / den | fp_div | 28 |
| S8 | b1m = m_i·mag, b2m = m_j·mag | 2x fp_mul | 4 |
| S9 | dx·b2m, dy·b2m, dz·b2m, dx·b1m, dy·b1m, dz·b1m | 6x fp_mul | 4 |
| | **total pipeline latency** | 18 FP units | **81** |

Shift-register delay lines carry dx/dy/dz, m_i, m_j, d2 and the pair index
alongside the computation.

### 5.2 Accumulation and position update
Velocity updates must be applied in pair order (a body appears in several
pairs and floating-point addition is not associative). The controller
applies the buffered pair results one pair at a time: 6 fp_add units update
vx/vy/vz of body i (subtract) and body j (add) in parallel (3 cycles + 1
write cycle per pair). Positions are then updated body by body with 3 fp_mul
(dt·v) followed by 3 fp_add (4 + 3 + 1 cycles per body).

### 5.3 Controller FSM
```
IDLE --START--> FEED --all pairs fed--> DRAIN --all results in--> ACC
ACC  --all pairs applied--> POS_MUL <-> POS_ADD --all bodies--> STEP_END
STEP_END --steps_done < NUM_STEPS--> FEED
STEP_END --steps_done == NUM_STEPS--> IDLE (DONE=1, irq)
```

### 5.4 Cycles per time step (measured)
Measured with the RTL system test (`tb/tb_nbody_accel.v`, CYCLES register) for
N = 2, 3, 5 and 16 bodies; all four fit exactly:
```
cycles per step = 6P + 11N + 84        (P = N(N-1)/2 pairs)
  84  : pair pipeline latency (81) + feed/drain control
  6P  : velocity accumulation, pair by pair
  11N : position update, body by body
N=5 (benchmark): 60 + 55 + 84 = 199 cycles x 10 ns = 1.99 us per step
```

### 5.5 Verification
- Floating-point operators: `tb/tb_fp_units.v`, 274k random and edge-case
  vectors against Python's IEEE-754 results, bit for bit, 0 errors.
- Whole accelerator, driven only through its MMIO registers
  (`tb/tb_nbody_accel.v`), against the golden model, which is itself checked
  bit for bit against the benchmark code (`nbody/optimized/sqrt`):
  N = 2, 3, 16 bodies, and the real benchmark scene, including a full
  benchmark call `advance(0.01, 20000)`: 3,980,000 cycles, all 35 values
  bit-identical.
- `run_tests.sh` rebuilds and reruns everything.


## 6. Software side
`hw/nbody_accel/sw/nbody_accel_driver.py`
- `advance = accelerated(software_advance)` wraps the benchmark's own
  function; the result is called exactly like it:
  `advance(dt, n, bodies, pairs)` (same signature, lists updated in place).
- If the device is present (PCIe BAR0 mmap-able), writes N, NUM_STEPS, DT and
  all body registers, sets START, waits for DONE (poll or interrupt), reads
  the body registers back into the Python lists.
- If not present, runs the software `advance()` unchanged (the benchmark
  never breaks, and changes stay inside a library, following the accelerator
  HW/SW interface rules from the course).
- For large N, the body state would be transferred with one DMA copy of a
  pinned host buffer (7 x 8 bytes per body) instead of per-register MMIO.

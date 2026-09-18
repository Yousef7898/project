# HW/SW co-design project: nbody and raytrace

Analysis, optimization and hardware acceleration of two
[pyperformance](https://github.com/python/pyperformance) benchmarks:
**nbody** and **raytrace**.

| Benchmark | Original (median) | Optimized (median) | Speedup | Output |
|---|---|---|---|---|
| nbody | 230.4 ms | 144.3 ms | **1.60x** (37% less time) | bit-identical |
| raytrace | 807.0 ms | 385.0 ms | **2.10x** (52% less time) | bit-identical image |

Hardware: an IEEE-754 double precision accelerator for nbody's whole
`advance()` loop, in Verilog, verified bit for bit against the benchmark;
estimated **5.7x** faster than the original software (3.5x faster than the
optimized software), including PCIe overhead.

Full write-ups: [`report_nbody.txt`](report_nbody.txt) and
[`report_raytrace.txt`](report_raytrace.txt).

---

## Repository structure

```
.
├── README.md                  this file
├── report_nbody.txt           report: nbody (analysis, optimizations, results, hardware)
├── report_raytrace.txt        report: raytrace
├── script_nbody.sh            full pipeline for nbody (setup, verify, profile, benchmark, compare)
├── script_raytrace.sh         full pipeline for raytrace
├── prompt.txt                 prompts used with the AI tool (Claude Code), in order
│
├── nbody/
│   ├── original/              unmodified benchmark from pyperformance 1.14.0
│   ├── optimized/
│   │   ├── locals/            FINAL: positions/velocities in local variables
│   │   ├── sqrt/              ** (-1.5) -> 1/(d2*sqrt(d2))  (no gain, dropped)
│   │   └── both/              locals + sqrt                 (dropped)
│   └── verify_nbody.py        checks every variant computes the same results
│
├── raytrace/
│   ├── original/              unmodified benchmark from pyperformance 1.14.0
│   ├── optimized/
│   │   ├── shadow_ray/        shadow ray built once, not once per object
│   │   ├── sphere_floats/     Sphere.intersectionTime with plain floats
│   │   ├── slots/             __slots__ on Vector and Point
│   │   └── combined/          FINAL: all three
│   └── verify_raytrace.py     checks every variant renders the same image
│
├── profiling/
│   ├── profile.sh             flame graph (pyperformance --hook perf_record),
│   │                          perf report (project guide command), perf stat
│   ├── pyspy_profile.sh       Python-level flame graph with py-spy
│   ├── workload.py            fixed amount of benchmark work (for counters, py-spy)
│   ├── summarize_flamegraph.py  flame graph -> top frames and time by category
│   ├── pyspy_fold.py          py-spy stacks -> benchmark-only flame graph input
│   └── summarize_pyspy.py     py-spy stacks -> hottest lines and functions
│
├── results/
│   ├── baseline*.json         baseline runs (default and --rigorous)
│   ├── nbody_*.json           rigorous runs of each nbody variant (two sessions)
│   ├── raytrace_*.json        rigorous runs of each raytrace variant
│   ├── *_commands.log         the exact commands used for those runs
│   └── profiling/<benchmark>/<original|optimized>/
│       ├── flamegraph.svg         flame graph from pyperformance (C level)
│       ├── flamegraph_summary.txt its widest frames and time by category
│       ├── stacks.folded          the stacks behind it
│       ├── pyspy_flamegraph.svg   Python-level flame graph (functions, lines)
│       ├── pyspy_top.txt          hottest Python lines and functions
│       ├── perf_report.txt        perf report --stdio
│       ├── perf_stat.txt          hardware counters
│       └── analysis.txt           bottleneck analysis (original versions)
│
└── hw/nbody_accel/            hardware accelerator for nbody
    ├── docs/
    │   ├── design.md          architecture: interfaces, register map, pipeline, FSM
    │   ├── performance.md     justification, speedup estimate, assumptions
    │   ├── tradeoffs.md       area estimate, performance/area/frequency/power trade-offs
    │   └── block_diagram.svg  block diagram (host, PCIe, accelerator)
    ├── rtl/                   Verilog: fp_add/mul/div/sqrt, pair_force, nbody_accel_top
    ├── tb/                    testbenches (FP units, whole accelerator via registers)
    ├── model/                 Python reference models, test vectors, speedup estimate
    ├── sw/                    host driver (PCIe BAR0, software fallback) + its test
    └── run_tests.sh           builds and runs every hardware test
```

Each optimized variant is a pyperformance benchmark of its own: a
`MANIFEST` plus `bm_<name>/run_benchmark.py`, so pyperformance can run it with
`--manifest`.

---

## Requirements

Developed and measured on the course QEMU VM: Ubuntu 22.04, 1 vCPU,
Python 3.10.12.

Software pipeline (`script_*.sh` installs these in step 1):
- `perf` (`linux-tools-common`, `linux-tools-$(uname -r)`)
- `python3-dbg` (debug build of Python, gives perf the interpreter's symbols)
- `pyperformance==1.14.0` (brings `pyperf`) and `py-spy`
- [FlameGraph](https://github.com/brendangregg/FlameGraph) scripts in `~/FlameGraph`
- root (perf and `pyperf system tune` need it)

Hardware tests:
- Icarus Verilog (`apt install iverilog`), tested with version 11
- `python3`

---

## How to run

### Benchmark pipelines

```bash
sudo ./script_nbody.sh
sudo ./script_raytrace.sh
```

Each script runs five steps and logs every command it runs:

1. **Environment setup**: installs the requirements above
2. **Correctness check**: `verify_nbody.py` / `verify_raytrace.py`
3. **Profiling** of the original and the final optimized version:
   flame graphs (pyperformance and py-spy), perf report, perf stat
4. **Benchmarks**: `pyperf system tune`, then `pyperformance run --rigorous`
   for the original and the optimized version, then `pyperf system reset`
5. **Comparison**: `pyperf compare_to`, statistics and histograms

Output goes to `results/runs/<benchmark>-<date>/`.

Options (environment variables):

| Variable | Effect |
|---|---|
| `SKIP_SETUP=1` | skip step 1 (requirements already installed) |
| `ALL_VARIANTS=1` | also benchmark every single optimization, not only the final one |
| `FAST=1` | quick check: `pyperformance --fast` (not for reported numbers) |
| `OUT=<dir>` | output directory |

Example, quick check of everything without reinstalling:
```bash
sudo SKIP_SETUP=1 FAST=1 ./script_raytrace.sh
```

A full rigorous run takes about 10 minutes for nbody and 20 minutes for
raytrace on the VM.

### Individual steps

```bash
# correctness of the optimized versions
python3 nbody/verify_nbody.py
python3 raytrace/verify_raytrace.py

# one optimized variant with pyperformance
python3 -m pyperformance run --rigorous --manifest nbody/optimized/locals/MANIFEST \
    -b nbody -o nbody_locals.json

# profiling of one version (writes results/profiling/<bench>/<version>/)
sudo profiling/profile.sh nbody original
sudo profiling/pyspy_profile.sh raytrace optimized

# compare the committed results
python3 -m pyperf compare_to --table results/nbody_original.json \
    results/nbody_locals.json results/nbody_sqrt.json results/nbody_both.json
python3 -m pyperf compare_to --table results/raytrace_original.json \
    results/raytrace_shadow_ray.json results/raytrace_sphere_floats.json \
    results/raytrace_slots.json results/raytrace_combined.json
```

### Hardware tests

```bash
hw/nbody_accel/run_tests.sh
```

Builds and runs (about 3 minutes), stopping at the first failure:

1. the floating-point operators against Python's IEEE-754 results,
   bit for bit (random and edge-case vectors)
2. the whole accelerator, driven only through its registers, on the real
   benchmark bodies and on 2, 3 and 16 bodies, bit for bit against the
   software, with the clock cycles per time step
3. the host driver: software fallback and offload

Options: `FP_VECTORS=<n>` (operator test cases, default 20000),
`BENCH_STEPS=<n>` (steps for the benchmark scene, default 200).
Logs go to `hw/nbody_accel/build/`.

Speedup estimate from the measured numbers:
```bash
python3 hw/nbody_accel/model/estimate_speedup.py
```

Using the accelerator from the benchmark (falls back to software when no
card is present):
```python
import nbody_accel_driver as accel      # hw/nbody_accel/sw/
advance = accel.accelerated(advance)    # the benchmark's own advance()
advance(0.01, 20000)
```

---

## Notes on the VM

- **Hardware-cycle sampling** records no samples in this VM, so perf sampling
  uses `-e cpu-clock` (999 samples per second of CPU time).
- **`pyperf system tune`** is needed for stable numbers on the single vCPU;
  its "Turbo Boost (MSR)" error is expected inside a VM. It also limits perf's
  sample rate, so profiling runs before it and `pyperf system reset` after.
- **Kernel frames** appear as `[unknown]` in the perf flame graphs (about 2%
  of samples): the VM's kernel is built without a symbol table.
- **Flame graph levels**: perf flame graphs show CPython's C functions (Python
  3.10 has no frame pointers, so no Python names); the py-spy flame graphs
  show the Python functions and lines. The reports use both.

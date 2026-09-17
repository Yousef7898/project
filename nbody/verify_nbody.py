"""Check that the optimized nbody variants compute the same results as the original.

Runs the same simulation as the benchmark (offset_momentum, report_energy,
advance(0.01, 20000), report_energy) in each variant, then compares the
energies and the final position/velocity of every body with the original.

IDENTICAL = bit-for-bit equal. OK = equal within 1e-6 relative: replacing
d2 ** -1.5 with 1/(d2*sqrt(d2)) changes rounding in the last bit (~1e-16 per
step), which accumulates to ~1e-9 over 20000 steps.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANTS = {
    "original": "original/run_benchmark.py",
    "locals": "optimized/locals/bm_nbody/run_benchmark.py",
    "sqrt": "optimized/sqrt/bm_nbody/run_benchmark.py",
    "both": "optimized/both/bm_nbody/run_benchmark.py",
}


def simulate(name, path):
    spec = importlib.util.spec_from_file_location("nbody_" + name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # fresh module -> fresh SYSTEM state
    mod.offset_momentum(mod.BODIES[mod.DEFAULT_REFERENCE])
    e_start = mod.report_energy()
    mod.advance(0.01, mod.DEFAULT_ITERATIONS)
    e_end = mod.report_energy()
    state = [v for (r, vel, m) in mod.SYSTEM for v in (*r, *vel)]
    return e_start, e_end, state


def main():
    ref = simulate("original", VARIANTS["original"])
    print(f"original: energy start={ref[0]!r} end={ref[1]!r}")
    ok = True
    for name, path in VARIANTS.items():
        if name == "original":
            continue
        res = simulate(name, path)
        values = [ref[0], ref[1]] + ref[2]
        got = [res[0], res[1]] + res[2]
        identical = values == got
        max_rel = max(abs(a - b) / abs(a) for a, b in zip(values, got) if a != 0)
        status = "IDENTICAL" if identical else ("OK" if max_rel < 1e-6 else "MISMATCH")
        ok &= status != "MISMATCH"
        print(f"{name:11}: energy end={res[1]!r}  max relative diff={max_rel:.2e}  -> {status}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

"""Test the accelerator driver against the benchmark software.

1. Fallback: with no device, the wrapped advance() is the software advance()
   (bit-identical to nbody/original).
2. Offload: with the register model device, running the benchmark through the
   driver gives the same result as the software with the same formula
   (nbody/optimized/sqrt), bit for bit, and differs from the original **
   version only by rounding.
3. Reports how many register (MMIO) operations one advance() call needs.

usage: python3 test_driver.py [steps]
"""
import importlib.util
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import nbody_accel_driver as accel  # noqa: E402


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.offset_momentum(mod.BODIES[mod.DEFAULT_REFERENCE])
    return mod


def state_bits(mod):
    return [struct.unpack(">Q", struct.pack(">d", v))[0]
            for (r, v, m) in mod.SYSTEM for v in (*r, *v, m)]


def state(mod):
    return [x for (r, v, m) in mod.SYSTEM for x in (*r, *v, m)]


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    ok = True

    # 1. no device -> software fallback, identical to the original
    ref = load("nbody/original/run_benchmark.py", "orig_ref")
    ref.advance(0.01, steps)
    mod = load("nbody/original/run_benchmark.py", "orig_fallback")
    adv = accel.accelerated(mod.advance, device=None)
    adv(0.01, steps)
    same = state_bits(mod) == state_bits(ref)
    ok &= same
    print(f"fallback (no device) == original software: {same}")

    # 2. register model device -> same as the sqrt formula software
    sqrt_ref = load("nbody/optimized/sqrt/bm_nbody/run_benchmark.py", "sqrt_ref")
    sqrt_ref.advance(0.01, steps)
    mod = load("nbody/original/run_benchmark.py", "orig_accel")
    dev = accel.RegisterModelDevice()
    adv = accel.accelerated(mod.advance, device=dev)
    adv(0.01, steps)
    same = state_bits(mod) == state_bits(sqrt_ref)
    ok &= same
    print(f"offloaded (register model) == nbody/optimized/sqrt: {same}")
    max_rel = max(abs(a - b) / abs(b) for a, b in zip(state(mod), state(ref)) if b != 0)
    print(f"offloaded vs original (** formula): max relative difference {max_rel:.2e}")
    print(f"energy: original {ref.report_energy():.15f}  offloaded {mod.report_energy():.15f}")

    # 3. host/device traffic for one advance() call
    print(f"MMIO register operations for one advance() call: {dev.mmio_ops} "
          f"(independent of the number of steps)")

    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

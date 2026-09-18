"""Golden model and system-test vectors for the nbody accelerator.

hw_advance() runs the benchmark's advance() loop with exactly the hardware's
operation order and formula (mag = dt / (d2 * sqrt(d2))). It is checked
bit for bit against the repository's software variant
nbody/optimized/sqrt (same formula), so the reference is the real benchmark
code, not only this model.

Writes tb/vectors/sys_<name>.hex:
  line 1: N            line 2: steps        line 3: dt (double bits)
  then 7*N lines of initial state (x y z vx vy vz m per body)
  then 7*N lines of expected state after `steps` steps

usage: python3 nbody_golden.py [benchmark_steps]
"""
import importlib.util
import math
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "..", "tb", "vectors")


def bits(x):
    return struct.unpack(">Q", struct.pack(">d", x))[0]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hw_advance(bodies, dt, n):
    """bodies: list of [x, y, z, vx, vy, vz, m]; updated in place."""
    nb = len(bodies)
    pairs = [(i, j) for i in range(nb - 1) for j in range(i + 1, nb)]
    for _ in range(n):
        for i, j in pairs:
            bi, bj = bodies[i], bodies[j]
            dx = bi[0] - bj[0]
            dy = bi[1] - bj[1]
            dz = bi[2] - bj[2]
            d2 = dx * dx + dy * dy + dz * dz
            mag = dt / (d2 * math.sqrt(d2))
            b1m = bi[6] * mag
            b2m = bj[6] * mag
            bi[3] -= dx * b2m
            bi[4] -= dy * b2m
            bi[5] -= dz * b2m
            bj[3] += dx * b1m
            bj[4] += dy * b1m
            bj[5] += dz * b1m
        for b in bodies:
            b[0] += dt * b[3]
            b[1] += dt * b[4]
            b[2] += dt * b[5]


def benchmark_state():
    """Initial state of the pyperformance nbody benchmark (after offset_momentum)."""
    mod = load(os.path.join(REPO, "nbody", "original", "run_benchmark.py"), "nbody_orig")
    mod.offset_momentum(mod.BODIES[mod.DEFAULT_REFERENCE])
    return [[*r, *v, m] for (r, v, m) in mod.SYSTEM]


def check_against_software(steps):
    """hw_advance must equal nbody/optimized/sqrt's advance() bit for bit."""
    mod = load(os.path.join(REPO, "nbody", "optimized", "sqrt", "bm_nbody", "run_benchmark.py"),
               "nbody_sqrt")
    mod.offset_momentum(mod.BODIES[mod.DEFAULT_REFERENCE])
    mod.advance(0.01, steps)
    sw = [[*r, *v, m] for (r, v, m) in mod.SYSTEM]
    hw = benchmark_state()
    hw_advance(hw, 0.01, steps)
    assert [bits(v) for b in sw for v in b] == [bits(v) for b in hw for v in b], \
        "golden model differs from nbody/optimized/sqrt"
    print(f"golden model == nbody/optimized/sqrt after {steps} steps (bit for bit)")


def random_state(rng, n):
    bodies = []
    for b in range(n):
        # bodies on separated shells so no close encounters
        r = 1.0 + 2.5 * b
        ang = rng.uniform(0, 2 * math.pi)
        bodies.append([r * math.cos(ang), r * math.sin(ang), rng.uniform(-0.5, 0.5),
                       rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), rng.uniform(-0.01, 0.01),
                       rng.uniform(1e-4, 40.0)])
    return bodies


def write(name, bodies, dt, steps):
    os.makedirs(OUT, exist_ok=True)
    init = [bits(v) for b in bodies for v in b]
    final = [list(b) for b in bodies]
    hw_advance(final, dt, steps)
    exp = [bits(v) for b in final for v in b]
    path = os.path.join(OUT, f"sys_{name}.hex")
    with open(path, "w") as f:
        f.write(f"{len(bodies):016x}\n{steps:016x}\n{bits(dt):016x}\n")
        for v in init + exp:
            f.write(f"{v:016x}\n")
    print(f"{path}: N={len(bodies)} steps={steps}")


def main():
    bench_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    check_against_software(bench_steps)
    rng = random.Random(2026)
    write("benchmark", benchmark_state(), 0.01, bench_steps)
    write("n2", random_state(rng, 2), 0.01, 50)
    write("n3", random_state(rng, 3), 0.005, 50)
    write("n16", random_state(rng, 16), 0.001, 10)


if __name__ == "__main__":
    main()

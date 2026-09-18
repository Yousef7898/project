"""Generate test vectors for the floating-point operators.

Python floats are IEEE-754 doubles and +, -, *, / and math.sqrt are
correctly rounded (round to nearest, ties to even), so Python is the
reference model for fp_add, fp_mul, fp_div and fp_sqrt.

Output files (one vector per line, hex):
  vectors/add.hex   : sub a b expected
  vectors/mul.hex   : a b expected
  vectors/div.hex   : a b expected
  vectors/sqrt.hex  : a expected

usage: python3 gen_fp_vectors.py [count]
"""
import math
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "tb", "vectors")


def bits(x):
    return struct.unpack(">Q", struct.pack(">d", x))[0]


def from_bits(b):
    return struct.unpack(">d", struct.pack(">Q", b))[0]


def supported(x):
    """Zero or a normal number (the operators' documented scope)."""
    b = bits(x)
    exp = (b >> 52) & 0x7FF
    return x == 0.0 or 0 < exp < 0x7FF


def rand_normal(rng, exp_range=(-300, 300)):
    sign = rng.getrandbits(1)
    exp = rng.randint(*exp_range) + 1023
    frac = rng.getrandbits(52)
    return from_bits((sign << 63) | (exp << 52) | frac)


def near(rng, x):
    """A value within a few ulps of x (exercises cancellation and ties)."""
    b = bits(x) + rng.randint(-4, 4)
    y = from_bits(b & 0xFFFFFFFFFFFFFFFF)
    return y if supported(y) else x


def workload_values(rng):
    """Values of the magnitudes nbody really uses."""
    return rng.choice([
        rng.uniform(-30, 30),            # positions
        rng.uniform(-0.05, 0.05),        # velocities
        rng.uniform(1e-5, 40),           # masses (up to 4*pi^2)
        0.01,                            # dt
        rng.uniform(1e-12, 1e-6),        # small deltas
    ])


def cases(rng, count):
    pool = []
    for _ in range(count):
        kind = rng.randrange(6)
        if kind == 0:
            a, b = rand_normal(rng), rand_normal(rng)
        elif kind == 1:
            a = rand_normal(rng); b = near(rng, a)             # cancellation
        elif kind == 2:
            a = rand_normal(rng); b = rand_normal(rng, (-60, 60)) * a  # large exponent gaps
        elif kind == 3:
            a, b = workload_values(rng), workload_values(rng)
        elif kind == 4:
            e = rng.randint(-20, 20)
            a = from_bits((rng.getrandbits(1) << 63) | ((1023 + e) << 52) | rng.getrandbits(52))
            b = from_bits((rng.getrandbits(1) << 63) | ((1023 + e + rng.randint(-2, 2)) << 52)
                          | rng.getrandbits(3))                 # few bits: exact ties
        else:
            a = rand_normal(rng, (-5, 5)); b = -a if rng.getrandbits(1) else a
        pool.append((a, b))
    specials = [0.0, -0.0, 1.0, -1.0, 2.0, 0.5, 3.0, 0.1, 0.01, 1.5,
                math.pi, 4 * math.pi ** 2, 1 - 2 ** -53, 1 + 2 ** -52]
    for a in specials:
        for b in specials:
            pool.append((a, b))
    return pool


def write(name, rows):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w") as f:
        for row in rows:
            f.write(" ".join(f"{v:016x}" for v in row) + "\n")
    print(f"{path}: {len(rows)} vectors")


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    rng = random.Random(12345)
    add, mul, div, sq = [], [], [], []
    for a, b in cases(rng, count):
        for sub in (0, 1):
            r = a - b if sub else a + b
            if supported(a) and supported(b) and supported(r):
                add.append((sub, bits(a), bits(b), bits(r)))
        r = a * b
        if supported(a) and supported(b) and supported(r):
            mul.append((bits(a), bits(b), bits(r)))
        if b != 0.0:
            r = a / b
            if supported(a) and supported(b) and supported(r):
                div.append((bits(a), bits(b), bits(r)))
        if supported(a) and not math.copysign(1.0, a) < 0 or a == 0.0:
            r = math.sqrt(a)
            if supported(r):
                sq.append((bits(a), bits(r)))
    write("add.hex", add)
    write("mul.hex", mul)
    write("div.hex", div)
    write("sqrt.hex", sq)


if __name__ == "__main__":
    main()

"""
N-body benchmark from the Computer Language Benchmarks Game.

This is intended to support Unladen Swallow's pyperf.py. Accordingly, it has been
modified from the Shootout version:
- Accept standard Unladen Swallow benchmark options.
- Run report_energy()/advance() in a loop.
- Reimplement itertools.combinations() to work with older Python versions.

Pulled from:
http://benchmarksgame.alioth.debian.org/u64q/program.php?test=nbody&lang=python3&id=1

Contributed by Kevin Carson.
Modified by Tupteq, Fredrik Johansson, and Daniel Nanz.
"""

from math import sqrt

import pyperf

__contact__ = "collinwinter@google.com (Collin Winter)"
DEFAULT_ITERATIONS = 20000
DEFAULT_REFERENCE = 'sun'


def combinations(l):
    """Pure-Python implementation of itertools.combinations(l, 2)."""
    result = []
    for x in range(len(l) - 1):
        ls = l[x + 1:]
        for y in ls:
            result.append((l[x], y))
    return result


PI = 3.14159265358979323
SOLAR_MASS = 4 * PI * PI
DAYS_PER_YEAR = 365.24

BODIES = {
    'sun': ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], SOLAR_MASS),

    'jupiter': ([4.84143144246472090e+00,
                 -1.16032004402742839e+00,
                 -1.03622044471123109e-01],
                [1.66007664274403694e-03 * DAYS_PER_YEAR,
                 7.69901118419740425e-03 * DAYS_PER_YEAR,
                 -6.90460016972063023e-05 * DAYS_PER_YEAR],
                9.54791938424326609e-04 * SOLAR_MASS),

    'saturn': ([8.34336671824457987e+00,
                4.12479856412430479e+00,
                -4.03523417114321381e-01],
               [-2.76742510726862411e-03 * DAYS_PER_YEAR,
                4.99852801234917238e-03 * DAYS_PER_YEAR,
                2.30417297573763929e-05 * DAYS_PER_YEAR],
               2.85885980666130812e-04 * SOLAR_MASS),

    'uranus': ([1.28943695621391310e+01,
                -1.51111514016986312e+01,
                -2.23307578892655734e-01],
               [2.96460137564761618e-03 * DAYS_PER_YEAR,
                2.37847173959480950e-03 * DAYS_PER_YEAR,
                -2.96589568540237556e-05 * DAYS_PER_YEAR],
               4.36624404335156298e-05 * SOLAR_MASS),

    'neptune': ([1.53796971148509165e+01,
                 -2.59193146099879641e+01,
                 1.79258772950371181e-01],
                [2.68067772490389322e-03 * DAYS_PER_YEAR,
                 1.62824170038242295e-03 * DAYS_PER_YEAR,
                 -9.51592254519715870e-05 * DAYS_PER_YEAR],
                5.15138902046611451e-05 * SOLAR_MASS)}


SYSTEM = list(BODIES.values())
PAIRS = combinations(SYSTEM)


def advance(dt, n, bodies=SYSTEM, pairs=PAIRS):
    if len(bodies) != 5:
        return _advance_generic(dt, n, bodies, pairs)

    # Copy positions, velocities and masses of the 5 bodies into local
    # variables once. Locals are ~2x faster to read/write than list items.
    (r0, v0, m0), (r1, v1, m1), (r2, v2, m2), (r3, v3, m3), (r4, v4, m4) = bodies
    x0, y0, z0 = r0
    vx0, vy0, vz0 = v0
    x1, y1, z1 = r1
    vx1, vy1, vz1 = v1
    x2, y2, z2 = r2
    vx2, vy2, vz2 = v2
    x3, y3, z3 = r3
    vx3, vy3, vz3 = v3
    x4, y4, z4 = r4
    vx4, vy4, vz4 = v4

    for _ in range(n):
        # pair (0, 1)
        dx = x0 - x1
        dy = y0 - y1
        dz = z0 - z1
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m0 * mag
        b2m = m1 * mag
        vx0 -= dx * b2m
        vy0 -= dy * b2m
        vz0 -= dz * b2m
        vx1 += dx * b1m
        vy1 += dy * b1m
        vz1 += dz * b1m
        # pair (0, 2)
        dx = x0 - x2
        dy = y0 - y2
        dz = z0 - z2
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m0 * mag
        b2m = m2 * mag
        vx0 -= dx * b2m
        vy0 -= dy * b2m
        vz0 -= dz * b2m
        vx2 += dx * b1m
        vy2 += dy * b1m
        vz2 += dz * b1m
        # pair (0, 3)
        dx = x0 - x3
        dy = y0 - y3
        dz = z0 - z3
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m0 * mag
        b2m = m3 * mag
        vx0 -= dx * b2m
        vy0 -= dy * b2m
        vz0 -= dz * b2m
        vx3 += dx * b1m
        vy3 += dy * b1m
        vz3 += dz * b1m
        # pair (0, 4)
        dx = x0 - x4
        dy = y0 - y4
        dz = z0 - z4
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m0 * mag
        b2m = m4 * mag
        vx0 -= dx * b2m
        vy0 -= dy * b2m
        vz0 -= dz * b2m
        vx4 += dx * b1m
        vy4 += dy * b1m
        vz4 += dz * b1m
        # pair (1, 2)
        dx = x1 - x2
        dy = y1 - y2
        dz = z1 - z2
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m1 * mag
        b2m = m2 * mag
        vx1 -= dx * b2m
        vy1 -= dy * b2m
        vz1 -= dz * b2m
        vx2 += dx * b1m
        vy2 += dy * b1m
        vz2 += dz * b1m
        # pair (1, 3)
        dx = x1 - x3
        dy = y1 - y3
        dz = z1 - z3
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m1 * mag
        b2m = m3 * mag
        vx1 -= dx * b2m
        vy1 -= dy * b2m
        vz1 -= dz * b2m
        vx3 += dx * b1m
        vy3 += dy * b1m
        vz3 += dz * b1m
        # pair (1, 4)
        dx = x1 - x4
        dy = y1 - y4
        dz = z1 - z4
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m1 * mag
        b2m = m4 * mag
        vx1 -= dx * b2m
        vy1 -= dy * b2m
        vz1 -= dz * b2m
        vx4 += dx * b1m
        vy4 += dy * b1m
        vz4 += dz * b1m
        # pair (2, 3)
        dx = x2 - x3
        dy = y2 - y3
        dz = z2 - z3
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m2 * mag
        b2m = m3 * mag
        vx2 -= dx * b2m
        vy2 -= dy * b2m
        vz2 -= dz * b2m
        vx3 += dx * b1m
        vy3 += dy * b1m
        vz3 += dz * b1m
        # pair (2, 4)
        dx = x2 - x4
        dy = y2 - y4
        dz = z2 - z4
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m2 * mag
        b2m = m4 * mag
        vx2 -= dx * b2m
        vy2 -= dy * b2m
        vz2 -= dz * b2m
        vx4 += dx * b1m
        vy4 += dy * b1m
        vz4 += dz * b1m
        # pair (3, 4)
        dx = x3 - x4
        dy = y3 - y4
        dz = z3 - z4
        d2 = dx * dx + dy * dy + dz * dz
        mag = dt / (d2 * sqrt(d2))
        b1m = m3 * mag
        b2m = m4 * mag
        vx3 -= dx * b2m
        vy3 -= dy * b2m
        vz3 -= dz * b2m
        vx4 += dx * b1m
        vy4 += dy * b1m
        vz4 += dz * b1m

        # update positions
        x0 += dt * vx0
        y0 += dt * vy0
        z0 += dt * vz0
        x1 += dt * vx1
        y1 += dt * vy1
        z1 += dt * vz1
        x2 += dt * vx2
        y2 += dt * vy2
        z2 += dt * vz2
        x3 += dt * vx3
        y3 += dt * vy3
        z3 += dt * vz3
        x4 += dt * vx4
        y4 += dt * vy4
        z4 += dt * vz4

    # Write the results back to the lists once, at the end.
    r0[0] = x0; r0[1] = y0; r0[2] = z0
    v0[0] = vx0; v0[1] = vy0; v0[2] = vz0
    r1[0] = x1; r1[1] = y1; r1[2] = z1
    v1[0] = vx1; v1[1] = vy1; v1[2] = vz1
    r2[0] = x2; r2[1] = y2; r2[2] = z2
    v2[0] = vx2; v2[1] = vy2; v2[2] = vz2
    r3[0] = x3; r3[1] = y3; r3[2] = z3
    v3[0] = vx3; v3[1] = vy3; v3[2] = vz3
    r4[0] = x4; r4[1] = y4; r4[2] = z4
    v4[0] = vx4; v4[1] = vy4; v4[2] = vz4


def _advance_generic(dt, n, bodies=SYSTEM, pairs=PAIRS):
    for i in range(n):
        for (([x1, y1, z1], v1, m1),
             ([x2, y2, z2], v2, m2)) in pairs:
            dx = x1 - x2
            dy = y1 - y2
            dz = z1 - z2
            d2 = dx * dx + dy * dy + dz * dz
            mag = dt / (d2 * sqrt(d2))
            b1m = m1 * mag
            b2m = m2 * mag
            v1[0] -= dx * b2m
            v1[1] -= dy * b2m
            v1[2] -= dz * b2m
            v2[0] += dx * b1m
            v2[1] += dy * b1m
            v2[2] += dz * b1m
        for (r, [vx, vy, vz], m) in bodies:
            r[0] += dt * vx
            r[1] += dt * vy
            r[2] += dt * vz


def report_energy(bodies=SYSTEM, pairs=PAIRS, e=0.0):
    for (((x1, y1, z1), v1, m1),
         ((x2, y2, z2), v2, m2)) in pairs:
        dx = x1 - x2
        dy = y1 - y2
        dz = z1 - z2
        e -= (m1 * m2) / ((dx * dx + dy * dy + dz * dz) ** 0.5)
    for (r, [vx, vy, vz], m) in bodies:
        e += m * (vx * vx + vy * vy + vz * vz) / 2.
    return e


def offset_momentum(ref, bodies=SYSTEM, px=0.0, py=0.0, pz=0.0):
    for (r, [vx, vy, vz], m) in bodies:
        px -= vx * m
        py -= vy * m
        pz -= vz * m
    (r, v, m) = ref
    v[0] = px / m
    v[1] = py / m
    v[2] = pz / m


def bench_nbody(loops, reference, iterations):
    # Set up global state
    offset_momentum(BODIES[reference])

    range_it = range(loops)
    t0 = pyperf.perf_counter()

    for _ in range_it:
        report_energy()
        advance(0.01, iterations)
        report_energy()

    return pyperf.perf_counter() - t0


def add_cmdline_args(cmd, args):
    cmd.extend(("--iterations", str(args.iterations)))


if __name__ == '__main__':
    runner = pyperf.Runner(add_cmdline_args=add_cmdline_args)
    runner.metadata['description'] = "n-body benchmark"
    runner.argparser.add_argument("--iterations",
                                  type=int, default=DEFAULT_ITERATIONS,
                                  help="Number of nbody advance() iterations "
                                       "(default: %s)" % DEFAULT_ITERATIONS)
    runner.argparser.add_argument("--reference",
                                  type=str, default=DEFAULT_REFERENCE,
                                  help="nbody reference (default: %s)"
                                       % DEFAULT_REFERENCE)

    args = runner.parse_args()
    runner.bench_time_func('nbody', bench_nbody,
                           args.reference, args.iterations)

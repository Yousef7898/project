"""Run a fixed amount of benchmark work, for perf stat counters.

pyperformance calibrates the number of loops to the speed of the code, so an
optimized version does more work per run. To compare hardware counters
(instructions, cache misses, ...) the work must be identical, so this script
calls the benchmark function directly with a fixed number of loops.

usage: python3 workload.py <nbody|raytrace> <path/to/run_benchmark.py> <loops>
"""
import importlib.util
import sys


def main():
    bench, path, loops = sys.argv[1], sys.argv[2], int(sys.argv[3])
    spec = importlib.util.spec_from_file_location("bm", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if bench == "nbody":
        mod.bench_nbody(loops, mod.DEFAULT_REFERENCE, mod.DEFAULT_ITERATIONS)
    elif bench == "raytrace":
        mod.bench_raytrace(loops, mod.DEFAULT_WIDTH, mod.DEFAULT_HEIGHT, None)
    else:
        sys.exit("unknown benchmark: " + bench)


if __name__ == "__main__":
    main()

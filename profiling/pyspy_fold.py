"""Turn py-spy's raw stacks into a readable benchmark flame graph input.

py-spy writes one line per unique stack:
    process;thread;func (file:line);func (file:line);... <samples>

For the flame graph we:
  1. keep only samples taken inside the benchmark function (bench_nbody or
     bench_raytrace), the same idea as pyperformance's perf_record hook
     (only the timed code): drops interpreter startup and imports, whose
     deep but very thin towers otherwise dominate the picture visually
  2. start every stack at the benchmark function (it becomes the root)
  3. name frames by function only, so the call tree is not split into
     separate boxes per calling line
  4. add the source line being executed as the top box, labelled with its
     code, e.g. "L88: v1[0] -= dx * b2m", so the hot lines are visible

usage: python3 pyspy_fold.py raw_stacks.folded run_benchmark.py > benchmark.folded
"""
import re
import sys

FRAME = re.compile(r"^(?P<func>.*?) \((?P<file>[^:()]+):(?P<line>\d+)\)$")


def main():
    raw_path, source_path = sys.argv[1], sys.argv[2]
    source = open(source_path).read().splitlines()
    source_name = source_path.rsplit("/", 1)[-1]

    kept = dropped = 0
    out = {}
    for raw in open(raw_path):
        raw = raw.rstrip("\n")
        if not raw:
            continue
        stack, _, count = raw.rpartition(" ")
        count = int(count)
        frames = stack.split(";")
        start = next((i for i, f in enumerate(frames) if f.startswith("bench_")), None)
        if start is None:
            dropped += count
            continue
        kept += count
        names = []
        for f in frames[start:]:
            m = FRAME.match(f)
            names.append(m.group("func") if m else f)
        leaf = FRAME.match(frames[-1])
        if leaf and leaf.group("file").endswith(source_name):
            n = int(leaf.group("line"))
            code = source[n - 1].strip() if 0 < n <= len(source) else ""
            names.append(f"L{n}: {code}".replace(";", ",")[:80])
        key = ";".join(names)
        out[key] = out.get(key, 0) + count

    for key, count in out.items():
        print(f"{key} {count}")
    total = kept + dropped
    print(f"pyspy_fold: kept {kept}/{total} samples ({100 * kept / max(total, 1):.1f}%) inside the "
          f"benchmark function, dropped {dropped} (startup, imports)", file=sys.stderr)


if __name__ == "__main__":
    main()

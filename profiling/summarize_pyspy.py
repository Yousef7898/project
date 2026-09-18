"""Summarize py-spy's collapsed Python stacks.

py-spy writes lines of the form
    process;thread;func (file.py:line);func (file.py:line);... <samples>

This prints:
  1. the hottest Python source lines (self time)
  2. the hottest Python functions (self time, lines merged)
  3. total time per function including everything it calls (inclusive time)

usage: python3 summarize_pyspy.py pyspy_stacks.folded [--top N]
"""
import argparse
import collections
import re

FRAME = re.compile(r"^(?P<func>.*?) \((?P<file>[^:]+):(?P<line>\d+)\)$")
SKIP_PREFIX = ("<frozen importlib", "<built-in>")


def parse(path):
    stacks = []
    with open(path) as f:
        for raw in f:
            raw = raw.rstrip("\n")
            if not raw:
                continue
            stack, _, count = raw.rpartition(" ")
            frames = stack.split(";")[2:]      # drop process and thread
            stacks.append((frames, int(count)))
    return stacks


def short(frame):
    m = FRAME.match(frame)
    if not m:
        return frame, frame
    func, file, line = m.group("func"), m.group("file").split("/")[-1], m.group("line")
    return f"{func} ({file}:{line})", f"{func} ({file})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folded")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    stacks = parse(args.folded)
    total = sum(c for _, c in stacks)
    self_line = collections.Counter()
    self_func = collections.Counter()
    incl_func = collections.Counter()

    for frames, count in stacks:
        if not frames:
            continue
        line_name, func_name = short(frames[-1])
        self_line[line_name] += count
        self_func[func_name] += count
        seen = set()
        for f in frames:
            _, fn = short(f)
            if fn not in seen:                 # count recursion once
                seen.add(fn)
                incl_func[fn] += count

    print(f"total samples: {total}")
    print()
    print(f"hottest source lines (self time, where the interpreter actually was):")
    for name, c in self_line.most_common(args.top):
        if name.startswith(SKIP_PREFIX):
            continue
        print(f"  {100 * c / total:6.2f}%  {name}")
    print()
    print("hottest functions (self time)")
    for name, c in self_func.most_common(args.top):
        if name.startswith(SKIP_PREFIX):
            continue
        print(f"  {100 * c / total:6.2f}%  {name}")
    print()
    print("functions including what they call (inclusive time)")
    for name, c in incl_func.most_common(args.top):
        if name.startswith(SKIP_PREFIX):
            continue
        print(f"  {100 * c / total:6.2f}%  {name}")


if __name__ == "__main__":
    main()

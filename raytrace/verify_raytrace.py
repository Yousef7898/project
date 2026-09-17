"""Check that the optimized raytrace variants render the same image as the original.

Each variant renders the benchmark scene (bench_raytrace with one loop) to a
PPM file; the raw pixel bytes are compared with the original's image.
"""
import hashlib
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANTS = {
    "original": "original/run_benchmark.py",
    "shadow_ray": "optimized/shadow_ray/bm_raytrace/run_benchmark.py",
    "sphere_floats": "optimized/sphere_floats/bm_raytrace/run_benchmark.py",
    "slots": "optimized/slots/bm_raytrace/run_benchmark.py",
    "combined": "optimized/combined/bm_raytrace/run_benchmark.py",
}
SIZES = [(100, 100), (200, 150)]  # benchmark default size + a larger image


def render(name, path, width, height):
    spec = importlib.util.spec_from_file_location("raytrace_" + name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "image.ppm")
        mod.bench_raytrace(1, width, height, out)
        with open(out, "rb") as f:
            return f.read()


def main():
    ok = True
    for width, height in SIZES:
        ref = render("original", VARIANTS["original"], width, height)
        print(f"{width}x{height}: original sha256={hashlib.sha256(ref).hexdigest()[:16]}")
        for name, path in VARIANTS.items():
            if name == "original":
                continue
            img = render(name, path, width, height)
            diff = sum(a != b for a, b in zip(img, ref)) + abs(len(img) - len(ref))
            status = "IDENTICAL" if img == ref else f"DIFFERENT ({diff} bytes)"
            ok &= img == ref
            print(f"  {name:14} sha256={hashlib.sha256(img).hexdigest()[:16]} -> {status}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

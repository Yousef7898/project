"""Summarize a flame graph's collapsed stacks (stacks.folded).

A flame graph is drawn from "collapsed stacks": one line per unique call
stack, "frame1;frame2;...;leaf <samples>". This script reads that file and
prints:

  1. the widest leaf frames (self time: where the CPU actually was)
  2. self time grouped into categories of CPython work, so the bottleneck
     type is visible at a glance (interpreter dispatch, function calls,
     attribute/dict lookups, float objects, list indexing, ...)

usage: python3 summarize_flamegraph.py stacks.folded [--top N]
"""
import argparse
import collections
import re

# Category rules, checked in order; the first matching pattern wins.
CATEGORIES = [
    ("interpreter loop (bytecode dispatch)", r"^_PyEval_EvalFrameDefault$"),
    ("debug-build checks (python3-dbg only)",
     r"_PyMem_Debug|read_size_t|write_size_t|pthread_getspecific|PyGILState_Check|is_tstate_valid"
     r"|_PyDict_CheckConsistency|_PyGILState_GetThisThreadState|PyThread_tss|_Py_CheckFunctionResult"
     r"|_Py_CheckSlotResult|validate_list|__memset|__errno_location|arena_map|address_in_range"),
    ("function calls (frames, call setup)",
     r"call_function|_PyEval_MakeFrameVector|_PyFrame_New|frame_dealloc|frame_alloc|_PyEval_Vector"
     r"|_PyObject_Vectorcall|_PyFunction_Vectorcall|method_vectorcall|_PyObject_MakeTpCall"
     r"|PyTuple_GetItem|tupledealloc|PyTuple_New|function_code_fastcall|_PyObject_Call"),
    ("attribute / dict lookups (instance __dict__)",
     r"lookdict|_PyDict_GetItem|_PyType_Lookup|_PyObject_GetMethod|insertdict|PyDict_SetItem"
     r"|PyDict_Contains|PyDict_GetItemWithError|_PyObjectDict_SetItem|new_dict|dict_dealloc"
     r"|_PyObject_GenericGetAttr|_PyObject_GenericSetAttr|PyObject_GetAttr|PyObject_SetAttr"
     r"|_PyUnicode_FromId|unicode_eq|PyType_IsSubtype"),
    ("list indexing (get/set item)",
     r"list_ass|list_subscript|list_item|PyObject_SetItem|PyObject_GetItem|PyNumber_AsSsize_t"
     r"|PyLong_AsSsize_t|_PyNumber_Index"),
    ("float objects (create/free)",
     r"PyFloat_FromDouble|float_dealloc|get_float_state|_Py_NewReference|_Py_Dealloc"),
    ("float arithmetic",
     r"float_(mul|add|sub|div|neg|pow|abs)|binary_i?op1?$|ternary_op|PyNumber_(Multiply|Add|Subtract"
     r"|InPlace\w+|Power|TrueDivide)"),
    ("math library (libm)", r"__ieee754|sqrt|pow_fma|^pow@|\[libm"),
    ("iteration", r"listiter|rangeiter|list_iter|PyObject_GetIter|PyIter_"),
    ("object creation (instances)",
     r"object_new|type_call|slot_tp_init|PyType_GenericAlloc|subtype_dealloc|object_dealloc"),
    ("memory allocator / GC", r"_PyMem|pymalloc|_PyObject_Malloc|_PyObject_Free|PyObject_Malloc"
     r"|PyObject_Free|_PyObject_GC|PyObject_GC|get_gc_state|malloc|free"),
    ("kernel / unresolved", r"^\[unknown\]$|^\[k\]|^0x|^\[python"),
]


def load(path):
    stacks = []
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            stack, _, count = line.rpartition(" ")
            stacks.append((stack.split(";"), int(count)))
    return stacks


def short(frame):
    return re.sub(r"\.lto_priv\.\d+$", "", frame)


def categorize(frame):
    for name, pattern in CATEGORIES:
        if re.search(pattern, frame):
            return name
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folded")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    stacks = load(args.folded)
    total = sum(c for _, c in stacks)
    self_time = collections.Counter()
    for frames, count in stacks:
        self_time[short(frames[-1])] += count

    print(f"total weight: {total} (sample periods)")
    print()
    print(f"top {args.top} frames by self time (flame graph leaf width):")
    for frame, count in self_time.most_common(args.top):
        print(f"  {100 * count / total:6.2f}%  {frame}")

    by_cat = collections.Counter()
    for frame, count in self_time.items():
        by_cat[categorize(frame)] += count
    print()
    print("self time by category:")
    for cat, count in by_cat.most_common():
        print(f"  {100 * count / total:6.2f}%  {cat}")


if __name__ == "__main__":
    main()

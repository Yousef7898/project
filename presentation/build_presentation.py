"""Build the project presentation (presentation/hwsw_project.pptx).

usage: python3 presentation/build_presentation.py
requires: pip install python-pptx

All numbers come from the repository (results/, report_*.txt, hw/nbody_accel/docs).
"""
import os

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "hwsw_project.pptx")

# ----------------------------------------------------------------------------
# Design: deep slate + copper (silicon / hardware), teal = "optimized / good"
# ----------------------------------------------------------------------------
DARK = "15202E"      # title / conclusion background
INK = "1E2A38"       # body text on light
MUTED = "5F6B7A"     # captions
CARD = "EEF2F6"      # card background on white
LINE = "C9D2DC"
COPPER = "D9822B"    # accent
TEAL = "1C9A86"      # optimized / good
GRAY = "9AA5B1"      # original / baseline
RED = "C0504D"       # worse
WHITE = "FFFFFF"
CODEBG = "1B2533"
CODEFG = "E6EDF3"

HEAD = "Cambria"
BODY = "Calibri"
MONO = "Courier New"

W, H = 13.333, 7.5


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
BLANK = prs.slide_layouts[6]


def new_slide(dark=False):
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = rgb(DARK if dark else WHITE)
    return s


def text(slide, x, y, w, h, paras, size=16, color=INK, font=BODY, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space_after=6, margin=0.05):
    """paras: str, or list of str / (str, dict) / list-of-runs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, Inches(margin))
    if isinstance(paras, str):
        paras = [paras]
    first = True
    for p in paras:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = align
        para.space_after = Pt(space_after)
        opts = {}
        runs = p
        if isinstance(p, tuple):
            runs, opts = p
        if isinstance(runs, str):
            runs = [(runs, {})]
        for r in runs:
            if isinstance(r, str):
                r = (r, {})
            t, ro = r
            for li, part in enumerate(t.split("\n")):
                if li:
                    para.add_line_break()          # real <a:br/>, not a character
                run = para.add_run()
                run.text = part
                f = run.font
                f.size = Pt(ro.get("size", opts.get("size", size)))
                f.bold = ro.get("bold", opts.get("bold", bold))
                f.italic = ro.get("italic", opts.get("italic", False))
                f.name = ro.get("font", opts.get("font", font))
                f.color.rgb = rgb(ro.get("color", opts.get("color", color)))
        if opts.get("bullet"):
            add_bullet(para, opts.get("level", 0))
    return tb


def add_bullet(para, level=0):
    pPr = para._p.get_or_add_pPr()
    indent = 228600 + level * 228600
    pPr.set("marL", str(indent))
    pPr.set("indent", str(-228600))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    bu = etree.SubElement(pPr, qn("a:buChar"))
    bu.set("char", "•")


def bullets(slide, x, y, w, h, items, size=16, color=INK, space_after=8):
    paras = []
    for it in items:
        if isinstance(it, tuple):
            runs, lvl = it
        else:
            runs, lvl = it, 0
        paras.append((runs, {"bullet": True, "level": lvl}))
    return text(slide, x, y, w, h, paras, size=size, color=color, space_after=space_after)


def box(slide, x, y, w, h, fill=CARD, line=None, radius=0.08, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    shp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(1)
    else:
        shp.line.fill.background()
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = radius
    shp.shadow.inherit = False
    return shp


def box_text(slide, x, y, w, h, paras, fill=CARD, line=None, size=14, color=INK,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, bold=False, radius=0.08,
             font=BODY, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    box(slide, x, y, w, h, fill, line, radius, shape)
    return text(slide, x, y, w, h, paras, size=size, color=color, align=align,
                anchor=anchor, bold=bold, font=font, space_after=2, margin=0.08)


def circle(slide, x, y, d, fill, label="", size=14, color=WHITE):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    shp.line.fill.background()
    shp.shadow.inherit = False
    if label:
        text(slide, x, y, d, d, label, size=size, color=color, bold=True,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, margin=0, space_after=0)
    return shp


def line(slide, x1, y1, x2, y2, color=MUTED, width=1.5, arrow=False, dash=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                                   Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    if dash:
        d = etree.SubElement(ln, qn("a:prstDash"))
        d.set("val", "dash")
    if arrow:
        t = etree.SubElement(ln, qn("a:tailEnd"))
        t.set("type", "triangle")
        t.set("w", "med")
        t.set("len", "med")
    return c


def title(slide, t, num=None, sub=None, dark=False):
    x = 0.6
    if num is not None:
        circle(slide, 0.6, 0.45, 0.55, COPPER, str(num), size=16)
        x = 1.35
    text(slide, x, 0.35, W - x - 0.6, 0.8, t, size=32, font=HEAD, bold=True,
         color=WHITE if dark else INK, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    if sub:
        text(slide, x, 1.1, W - x - 0.6, 0.45, sub, size=16,
             color="B8C4D2" if dark else MUTED, space_after=0)


def code(slide, x, y, w, h, lines, size=12):
    box(slide, x, y, w, h, CODEBG, radius=0.04)
    return text(slide, x + 0.1, y + 0.08, w - 0.2, h - 0.16, lines, size=size,
                font=MONO, color=CODEFG, space_after=0)


def stat(slide, x, y, w, value, label, color=TEAL, vsize=40, lsize=13, dark=False):
    text(slide, x, y, w, 0.8, value, size=vsize, bold=True, color=color, font=HEAD,
         space_after=0, anchor=MSO_ANCHOR.BOTTOM)
    text(slide, x, y + 0.82, w, 0.7, label, size=lsize,
         color="C9D3DE" if dark else MUTED, space_after=0)


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def style_chart(chart, colors, number_format='0.0', font_size=12, legend=False,
                gap=60, label_color=INK):
    chart.font.size = Pt(font_size)
    chart.font.name = BODY
    chart.font.color.rgb = rgb(INK)
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
    plot = chart.plots[0]
    plot.gap_width = gap
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = number_format
    dl.number_format_is_linked = False
    dl.font.size = Pt(font_size)
    dl.font.color.rgb = rgb(label_color)
    try:
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
    except Exception:
        pass
    va = chart.value_axis
    va.has_major_gridlines = False
    va.visible = False
    ca = chart.category_axis
    ca.format.line.color.rgb = rgb(LINE)
    ca.tick_labels.font.size = Pt(font_size)
    ca.tick_labels.font.color.rgb = rgb(INK)
    for i, s in enumerate(chart.series):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(colors[i % len(colors)])


def color_points(series, colors):
    for i, c in enumerate(colors):
        pt = series.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(c)


def bar_chart(slide, x, y, w, h, cats, series, colors, horizontal=False, fmt='0.0',
              point_colors=None, legend=False, font_size=12, gap=60):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    style_chart(ch, colors, fmt, font_size, legend, gap)
    if horizontal:
        ch.category_axis.reverse_order = True
    if point_colors:
        color_points(ch.series[0], point_colors)
    return ch


# ============================================================================
# 1. Title
# ============================================================================
s = new_slide(dark=True)
text(s, 0.8, 1.2, 11.5, 0.5, "046882 HW/SW Co-design  ·  Final project", size=16, color=COPPER,
     bold=True, space_after=0)
text(s, 0.8, 1.75, 11.5, 1.6, "Faster Python: nbody & raytrace", size=48, font=HEAD, bold=True,
     color=WHITE, space_after=0)
text(s, 0.8, 3.0, 11.5, 0.9,
     "Profiling, software optimization and a hardware accelerator for pyperformance benchmarks",
     size=20, color="C9D3DE", space_after=0)
text(s, 0.8, 3.75, 11.5, 0.45, "Student 1: Yousef Atrash    ·    Student 2: Housin Mohammed Agbaria",
     size=18, color=WHITE, bold=True, space_after=0)
stat(s, 0.8, 4.4, 3.4, "1.60x", "nbody, software optimization\nidentical results", COPPER, 44, 14, True)
stat(s, 4.6, 4.4, 3.4, "2.10x", "raytrace, software optimization\nidentical image", COPPER, 44, 14, True)
stat(s, 8.4, 4.4, 4.2, "5.7x", "nbody, hardware accelerator\n(estimate, incl. PCIe overhead)", COPPER, 44, 14, True)
text(s, 0.8, 6.55, 11.5, 0.4, "Draft: this presentation is not final and will be finalized before the presentation day.",
     size=12, color="8FA0B3", space_after=0)
notes(s, "Introduce the project: two pyperformance benchmarks, nbody (a physics simulation) "
         "and raytrace (a small ray tracer). We profiled both, optimized them in Python, and "
         "designed a hardware accelerator for nbody. The three numbers are the headline results; "
         "every one of them is backed by measurements we will show.")

# ============================================================================
# 2. Project flow
# ============================================================================
s = new_slide()
title(s, "How we worked", sub="The talk follows the same order as the project")
steps = [("Understand", "read the code,\ndata structures"),
         ("Measure", "pyperformance\nbaseline"),
         ("Profile", "perf, flame graphs,\npy-spy, counters"),
         ("Optimize", "one change at a time,\nmeasure each"),
         ("Verify", "output must stay\nbit-identical"),
         ("Accelerate", "Verilog accelerator\nfor nbody")]
x0, step_w = 0.7, 2.02
for i, (t, d) in enumerate(steps):
    x = x0 + i * step_w
    circle(s, x + 0.55, 2.2, 0.9, COPPER if i in (2, 5) else DARK, str(i + 1), size=22)
    if i < len(steps) - 1:
        line(s, x + 1.5, 2.65, x + step_w + 0.5, 2.65, LINE, 2, arrow=True)
    text(s, x, 3.3, 2.0, 0.5, t, size=20, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
    text(s, x, 3.8, 2.0, 1.0, d, size=14, color=MUTED, align=PP_ALIGN.CENTER)
box_text(s, 0.7, 5.3, 11.9, 1.2,
         [[("Rule we kept throughout: ", {"bold": True}),
           "every change is its own variant, measured on its own with pyperformance --rigorous, "
           "and checked to give exactly the same output as the original."]],
         fill=CARD, size=16, align=PP_ALIGN.LEFT)
notes(s, "This is the structure of the talk and of our work. Profiling (3) drives the "
         "optimizations (4), and every optimization is verified (5) before we trust its number. "
         "The accelerator (6) is designed for the part that software cannot fix.")

# ============================================================================
# 3. Measurement setup
# ============================================================================
s = new_slide()
title(s, "Measuring on a noisy single-CPU VM", num=1,
      sub="If the noise is bigger than the effect, the result means nothing")
bullets(s, 0.7, 1.8, 6.2, 4.5, [
    [("Environment: ", {"bold": True}), "course QEMU image, Ubuntu 22.04, 1 vCPU, Python 3.10.12, pyperformance 1.14.0"],
    [("Timing: ", {"bold": True}), "pyperformance run --rigorous: 20 processes x 3 values = 120 samples per benchmark"],
    [("Stability: ", {"bold": True}), "pyperf system tune (CPU pinning, IRQs moved away) before every timing session"],
    [("Statistics: ", {"bold": True}), "median and MAD (robust to outliers), mean and std, histograms"],
    [("Correctness: ", {"bold": True}), "verify scripts compare every result bit for bit with the original"],
], size=16)
box(s, 7.4, 1.8, 5.3, 4.6, CARD)
text(s, 7.7, 1.95, 4.8, 0.5, "raytrace baseline spread", size=16, bold=True)
stat(s, 7.7, 2.5, 2.3, "±84 ms", "first default run\n(±10%, bigger than\nthe 7% target)", RED, 34, 13)
stat(s, 10.2, 2.5, 2.3, "±19 ms", "tuned + rigorous\n(±2%, 120 samples)", TEAL, 34, 13)
text(s, 7.7, 4.7, 4.8, 1.5,
     "The long tail of slow runs came from the VM being interrupted, not from the benchmark: "
     "the median barely moved (816 -> 809 ms), the tail disappeared.",
     size=14, color=MUTED)
notes(s, "Before optimizing anything we made sure we could trust our numbers. The first raytrace "
         "run had a spread of plus-minus 10 percent, larger than the 7 percent improvement the "
         "project asks for. Tuning the VM and taking 120 samples brought it to 2 percent. We "
         "report medians because a few interrupted runs pull the mean up.")

# ============================================================================
# 4. nbody overview
# ============================================================================
s = new_slide()
title(s, "nbody: planets under gravity", num=2,
      sub="Sun + 4 giant planets, 20000 time steps per benchmark iteration")
# orbit diagram: 5 bodies, 10 pair lines
import math as _m
cx, cy, r = 3.3, 4.2, 1.9
pos = [(cx + r * _m.cos(_m.radians(90 + 72 * k)), cy - r * _m.sin(_m.radians(90 + 72 * k))) for k in range(5)]
for i in range(5):
    for j in range(i + 1, 5):
        line(s, pos[i][0], pos[i][1], pos[j][0], pos[j][1], LINE, 1.25)
names = ["Sun", "Jupiter", "Saturn", "Uranus", "Neptune"]
for k, (px, py) in enumerate(pos):
    d = 0.62 if k == 0 else 0.46
    circle(s, px - d / 2, py - d / 2, d, COPPER if k == 0 else DARK)
    text(s, px - 0.8, py + d / 2 + 0.02, 1.6, 0.35, names[k], size=12, color=MUTED, align=PP_ALIGN.CENTER)
text(s, 0.7, 6.55, 5.3, 0.5, "10 pairs per step  ·  O(N²) pair loop", size=14, color=MUTED,
     align=PP_ALIGN.CENTER)
code(s, 6.6, 1.8, 6.1, 3.25, [
    "def advance(dt, n, bodies, pairs):",
    "  for i in range(n):",
    "    for (([x1,y1,z1], v1, m1),",
    "         ([x2,y2,z2], v2, m2)) in pairs:",
    "      dx = x1-x2; dy = y1-y2; dz = z1-z2",
    "      mag = dt * (dx*dx+dy*dy+dz*dz)**(-1.5)",
    "      v1[0] -= dx * m2 * mag   # ... y, z",
    "      v2[0] += dx * m1 * mag   # ... y, z",
    "    for (r, [vx, vy, vz], m) in bodies:",
    "      r[0] += dt * vx          # ... y, z",
], size=12)
bullets(s, 6.6, 5.25, 6.1, 1.8, [
    [("Data: ", {"bold": True}), "each body = ([x,y,z], [vx,vy,vz], mass), lists updated in place"],
    [("Libraries: ", {"bold": True}), "none, plain Python floats (pyperf only for timing)"],
], size=14, space_after=4)
notes(s, "nbody is the classic N-body program. Each step computes the gravitational pull for "
         "all 10 pairs of bodies, updates velocities, then positions. Positions and velocities "
         "are small Python lists that are updated in place. There is no numeric library: every "
         "operation is a Python float operation. Keep this code in mind: the lists are the key.")

# ============================================================================
# 5. raytrace overview
# ============================================================================
s = new_slide()
title(s, "raytrace: a ray tracer in pure Python", num=2,
      sub="100 x 100 image: 7 spheres, a checkerboard floor, 2 lights")
# scene diagram
cam = (0.9, 4.3)
circle(s, cam[0] - 0.2, cam[1] - 0.2, 0.4, DARK)
text(s, 0.4, 4.6, 1.2, 0.3, "camera", size=12, color=MUTED, align=PP_ALIGN.CENTER)
sph = (4.0, 3.6)
circle(s, sph[0] - 0.7, sph[1] - 0.7, 1.4, COPPER)
text(s, 3.3, 4.35, 1.4, 0.3, "sphere", size=12, color=MUTED, align=PP_ALIGN.CENTER)
floor_y = 5.9
line(s, 0.7, floor_y, 6.2, floor_y, DARK, 3)
text(s, 4.6, 5.95, 1.6, 0.3, "floor", size=12, color=MUTED)
hit = (3.37, 3.95)
line(s, cam[0] + 0.2, cam[1] - 0.05, hit[0], hit[1], TEAL, 2.25, arrow=True)
line(s, hit[0], hit[1], 2.2, 5.9, DARK, 1.5, arrow=True, dash=True)
lights = [(5.6, 2.0), (1.9, 1.8)]
for lx, ly in lights:
    circle(s, lx - 0.17, ly - 0.17, 0.34, "F2C14E")
    line(s, hit[0], hit[1], lx, ly, "E0A43A", 1.5, arrow=True, dash=True)
text(s, 2.35, 1.55, 3.0, 0.3, "shadow rays to each light", size=12, color="B07A1E")
text(s, 2.75, 5.2, 2.4, 0.3, "reflection (recursive)", size=12, color=INK)
text(s, 1.2, 4.3, 2.0, 0.3, "camera ray", size=12, color=TEAL)
bullets(s, 6.9, 1.8, 5.8, 5.2, [
    [("Per pixel: ", {"bold": True}), "closest hit -> colour = reflection + diffuse + ambient"],
    ["reflection: rayColour calls itself again (up to 4 levels deep)"],
    ["diffuse: one shadow ray per light, tested against every object"],
    [("Data: ", {"bold": True}), "Vector and Point classes (x, y, z) with tiny methods: dot, scale, "
     "__sub__, plus no-op type checks (mustBeVector, isPoint)"],
    ["almost every arithmetic step creates a new Vector object"],
    [("Libraries: ", {"bold": True}), "math, array (pixel buffer), pyperf"],
], size=17, space_after=12)
notes(s, "raytrace renders a small image. For each pixel it finds the closest object, then "
         "computes colour from a reflected ray (recursion), shadow rays to the two lights, and "
         "ambient light. The code is very object-oriented: Vector and Point objects with small "
         "methods. Remember the shadow rays and the Vector objects: that is where the time goes.")

# ============================================================================
# 6. Profiling toolbox
# ============================================================================
s = new_slide()
title(s, "Our profiling toolbox", num=3,
      sub="Flame graphs show WHERE the time goes; counters and the code show WHY")
cards = [
    ("perf report", "project guide command, python3-dbg",
     "Which CPython C functions run: dispatch, list access, dict lookups, calls"),
    ("Flame graph (pyperformance)", "pyperformance --hook perf_record",
     "The same, as a picture; only the timed benchmark code is recorded"),
    ("Flame graph (py-spy)", "samples Python's own frames",
     "Python function names and source lines, with the call tree"),
    ("perf stat", "hardware counters, fixed work",
     "Instructions, IPC, cache misses, branch misses: memory or compute?"),
]
for i, (t, sub_, d) in enumerate(cards):
    x = 0.7 + (i % 2) * 6.1
    y = 1.85 + (i // 2) * 2.25
    box(s, x, y, 5.8, 2.0, CARD)
    circle(s, x + 0.25, y + 0.3, 0.5, COPPER if i in (1, 2) else DARK, str(i + 1), size=14)
    text(s, x + 0.95, y + 0.2, 4.7, 0.45, t, size=18, bold=True, font=HEAD, space_after=0)
    text(s, x + 0.95, y + 0.65, 4.7, 0.4, sub_, size=13, color=COPPER, space_after=0)
    text(s, x + 0.95, y + 1.05, 4.7, 0.9, d, size=14, color=INK, space_after=0)
text(s, 0.7, 6.4, 12, 0.6,
     "Plus cProfile for call counts, and small timeit/dis experiments to confirm a suspect "
     "before changing code.  Python 3.10 has no frame pointers, so perf cannot name Python "
     "functions: that is why we added py-spy.",
     size=13, color=MUTED)
notes(s, "We used four complementary tools. perf report is the command from the project guide; "
         "with python3-dbg it names the interpreter's C functions. pyperformance's perf_record "
         "hook generates the flame graph the project asks for. Because Python 3.10 has no frame "
         "pointers, those flame graphs have no Python names, so we added py-spy, which shows "
         "functions and lines. perf stat tells us whether we are memory-bound or not.")

# ============================================================================
# 7. nbody profile
# ============================================================================
s = new_slide()
title(s, "nbody: where the time goes", num=3,
      sub="The math is cheap. The interpreter around it is not.")
ch = bar_chart(s, 0.5, 1.75, 6.4, 4.4,
               ["interpreter loop", "float arithmetic", "list indexing", "float objects", "pow (**)"],
               [("share of time (%)", (44.9, 19.4, 14.8, 12.9, 1.8))],
               [GRAY], horizontal=True, point_colors=[GRAY, GRAY, COPPER, GRAY, TEAL], fmt='0.0"%"')
text(s, 0.7, 6.2, 6.2, 0.7, "C-level flame graph (pyperformance), self time. "
     "Counters: IPC 2.94, cache misses 4.3%, branch misses 0.37%: not memory, not branches.",
     size=12, color=MUTED)
box(s, 7.3, 1.8, 5.4, 4.9, CARD)
text(s, 7.55, 1.95, 5.0, 0.4, "py-spy: hottest lines of advance()", size=16, bold=True)
rows = [("48.3%", "v1[0] -= dx*b2m ... v2[2] += dz*b1m", COPPER),
        ("18.3%", "mag = dt * (d2) ** (-1.5)", INK),
        ("10.6%", "r[0] += dt * vx  ...", COPPER),
        ("8.4%", "for ((x1,y1,z1),v1,m1), ... in pairs", INK)]
for k, (v, t, c) in enumerate(rows):
    yy = 2.55 + k * 0.95
    text(s, 7.55, yy, 1.4, 0.6, v, size=26, bold=True, color=c, font=HEAD, space_after=0)
    text(s, 9.0, yy + 0.08, 3.6, 0.8, t, size=13, font=MONO, color=INK, space_after=0)
text(s, 7.55, 6.3, 5.0, 0.4, "list read/write lines: ~59% of the run time", size=13,
     bold=True, color=COPPER)
notes(s, "Left: the flame graph from pyperformance, grouped by kind of work. Almost half is the "
         "bytecode dispatch loop; list indexing is 15 percent; pow, the one expensive math "
         "function, is only 1.8 percent. Right: py-spy shows the same thing per Python line: the "
         "six velocity-update lines alone are 48 percent. The counters say it is not a memory "
         "problem: the CPU just executes many instructions per float operation.")

# ============================================================================
# 8. Why lists hurt
# ============================================================================
s = new_slide()
title(s, "Why v[0] -= x is expensive", num=3,
      sub="Checked with dis and timeit before changing any code")
code(s, 0.7, 1.85, 5.6, 2.4, [
    "# local variable: x",
    "LOAD_FAST   x",
    "",
    "# list element: v[0]",
    "LOAD_FAST   v",
    "LOAD_CONST  0",
    "BINARY_SUBSCR     # type check, index check",
], size=14)
text(s, 0.7, 4.45, 5.6, 2.2,
     "A list element costs extra bytecodes and C calls (type check, index conversion, "
     "fetch). nbody does 75 list reads and 75 list writes per step, 20000 steps per call.",
     size=15)
ch = bar_chart(s, 6.8, 1.75, 6.0, 4.6, ["read", "update (-=)"],
               [("local variable", (17, 38)), ("list element", (33, 80))],
               [TEAL, GRAY], legend=True, fmt='0" ns"', font_size=13, gap=80)
text(s, 6.9, 6.4, 5.8, 0.5, "timeit on the VM, nanoseconds per operation", size=12, color=MUTED)
notes(s, "This is the experiment that told us what to do. A local variable is one LOAD_FAST, "
         "a slot in the frame. A list element is three bytecodes plus type and bounds checks. "
         "Reading is 2 times slower, updating too. One access is only 40 nanoseconds extra, but "
         "nbody does 1.2 million list updates per run, so it adds up.")

# ============================================================================
# 9. nbody optimization
# ============================================================================
s = new_slide()
title(s, "nbody fix: keep the state in local variables", num=4,
      sub="Copy once at the start of advance(), compute on locals, write back once at the end")
code(s, 0.7, 1.85, 6.3, 2.9, [
    "(r0, v0, m0), ... (r4, v4, m4) = bodies",
    "x0, y0, z0 = r0;  vx0, vy0, vz0 = v0   # ...",
    "for _ in range(n):",
    "    # pair (0, 1)",
    "    dx = x0 - x1; dy = y0 - y1; dz = z0 - z1",
    "    mag = dt * ((dx*dx+dy*dy+dz*dz)**(-1.5))",
    "    vx0 -= dx * (m1*mag)   # locals only",
    "    # ... 9 more pairs, then positions",
    "r0[0] = x0; v0[0] = vx0   # write back once",
], size=13)
text(s, 0.7, 4.95, 6.3, 1.3,
     "Same operations in the same order, so the output is bit-for-bit identical "
     "(verify_nbody.py, 20000 steps). Other body counts fall back to the original loop.",
     size=14, color=MUTED)
stat(s, 7.6, 1.8, 2.5, "1.60x", "faster\n230.4 -> 144.3 ms median", TEAL, 48, 14)
stat(s, 10.3, 1.8, 2.5, "-34%", "instructions\n(perf stat, same work)", TEAL, 48, 14)
stat(s, 7.6, 4.1, 2.5, "0%", "list indexing left in the\nflame graph (was 14.8%)", TEAL, 48, 14)
stat(s, 10.3, 4.1, 2.5, "1.65x", "second session:\nreproducible", TEAL, 48, 14)
notes(s, "The fix follows directly from the profile. We copy positions and velocities into "
         "local variables once, run all 20000 steps on locals, and write back once. Because the "
         "operations and their order are unchanged, the result is bit-identical. 1.60 times "
         "faster, a third fewer instructions, and list indexing disappears from the flame graph. "
         "Trade-off: the 10 pairs are written out, so it is specialised to 5 bodies with a "
         "fallback for other sizes.")

# ============================================================================
# 10. The sqrt lesson
# ============================================================================
s = new_slide()
title(s, "A change that did not help: ** -> sqrt", num=4,
      sub="mag = dt / (d2 * sqrt(d2)) is mathematically the same as dt * d2 ** (-1.5)")
stat(s, 0.8, 1.9, 3.6, "1.8%", "pow's share of the time:\nthe profile predicted\n≤ 2% gain", COPPER, 54, 15)
stat(s, 4.9, 1.9, 3.6, "1.01x", "slower when measured\n(and locals+sqrt slower\nthan locals alone)", RED, 54, 15)
stat(s, 9.0, 1.9, 3.6, "n.s.", "sqrt as a local variable:\n143.3 vs 143.7 ms,\nnot significant", GRAY, 54, 15)
box(s, 0.7, 4.6, 12.0, 1.75, CARD)
text(s, 1.0, 4.75, 11.4, 1.55, [
    [("Why: ", {"bold": True}), "in Python the cost is not the math. d2 ** (-1.5) is one bytecode that "
     "calls C pow directly (86 ns); 1/(d2*sqrt(d2)) needs a lookup of sqrt, a call, a multiply "
     "and a divide (93 ns)."],
    [("Decision: ", {"bold": True}), "dropped, kept **. The measurement stays in the report as a "
     "negative result that the profile correctly predicted."],
], size=16, space_after=8)
notes(s, "sqrt is one CPU instruction, so replacing pow looked like a win. The flame graph "
         "said otherwise: pow is only 1.8 percent of the time. Measured, it was 1 percent slower, "
         "because calling sqrt from Python costs more than pow saves. Even making sqrt a local "
         "variable gave no significant difference. Lesson: measure, do not assume.")

# ============================================================================
# 11. raytrace profile
# ============================================================================
s = new_slide()
title(s, "raytrace: where the time goes", num=3,
      sub="Python-level flame graph (py-spy): width = share of run time")
# mini flame graph (icicle, drawn as stacked bars)
fx, fw, fy, fh = 0.7, 7.6, 1.85, 0.52
fbase = fy + 4 * (fh + 0.06)                     # root row at the bottom, like a flame graph
levels = [
    [("bench_raytrace > render", 0, 99.7, DARK)],
    [("rayColour", 0, 89.4, "3A4A5E")],
    [("colourAt", 0, 67.4, "54667C"), ("listcomp: intersect all", 67.4, 19.0, "6F8299")],
    [("_lightIsVisible (shadow rays)", 0, 45.9, COPPER), ("rayColour (reflect)", 45.9, 21.5, "8C9BAD")],
    [("Ray() built again", 0, 27.6, RED), ("intersect", 27.6, 17.5, "E0A43A")],
]
for li, lv in enumerate(levels):
    for (lbl, start, width, col) in lv:
        bx = fx + fw * start / 100
        bw = fw * width / 100 - 0.04
        box_text(s, bx, fbase - li * (fh + 0.06), bw, fh, lbl, fill=col, size=12, color=WHITE,
                 radius=0.1, align=PP_ALIGN.LEFT)
text(s, 0.7, 5.1, 7.6, 1.6, [
    [("intersectionTime ", {"bold": True}), "from all callers: 43% (dot 20%, __sub__ 22%)"],
    [("C level: ", {"bold": True}), "function calls 19.8%, dict lookups 17.7%, math 0.1%"],
    [("cProfile: ", {"bold": True}), "3.09 million Python calls and 453k new Vectors per image"],
], size=14, space_after=5)
box(s, 8.8, 1.85, 3.9, 4.0, CARD)
text(s, 9.05, 2.0, 3.5, 0.4, "Bottlenecks", size=18, bold=True, font=HEAD)
bullets(s, 9.05, 2.5, 3.5, 3.3, [
    ["the same shadow ray rebuilt for every object (~28%)"],
    ["~7 tiny method calls and a temporary Vector per ray-object test"],
    ["every Vector/Point has its own attribute dictionary"],
], size=16, space_after=12)
notes(s, "This is a simplified copy of the py-spy flame graph. Nearly half the time is in "
         "_lightIsVisible, the shadow-ray check, and more than half of that is building the same "
         "Ray object again for every object in the scene. intersectionTime is 43 percent, mostly "
         "its small helper methods. At C level the picture is calls and dictionary lookups; "
         "the math itself is almost free. Unlike nbody, the problem is the object-oriented structure.")

# ============================================================================
# 12. raytrace optimizations
# ============================================================================
s = new_slide()
title(s, "raytrace fixes: three targeted changes", num=4,
      sub="Each measured on its own, each renders a bit-identical image")
fixes = [("shadow_ray", "Build Ray(p, l - p) once per light, not once per object", "1.30x"),
         ("sphere_floats", "intersectionTime with plain floats: no temporary Vector, no dot/__sub__ calls", "1.34x"),
         ("slots", "__slots__ = ('x','y','z'): no per-object dictionary", "1.12x")]
for i, (n, d, sp) in enumerate(fixes):
    y = 1.85 + i * 1.3
    box(s, 0.7, y, 5.9, 1.1, CARD)
    text(s, 0.95, y + 0.1, 3.6, 0.45, n, size=17, bold=True, font=MONO, space_after=0)
    text(s, 0.95, y + 0.52, 4.3, 0.55, d, size=13, color=MUTED, space_after=0)
    text(s, 5.0, y + 0.15, 1.5, 0.8, sp, size=26, bold=True, color=TEAL, font=HEAD,
         align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
box(s, 0.7, 5.75, 5.9, 1.0, DARK)
text(s, 0.95, 5.8, 3.6, 0.9, "combined", size=20, bold=True, font=MONO, color=WHITE,
     anchor=MSO_ANCHOR.MIDDLE, space_after=0)
text(s, 5.0, 5.8, 1.5, 0.9, "2.10x", size=30, bold=True, color=COPPER, font=HEAD,
     align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE, space_after=0)
ch = bar_chart(s, 7.0, 1.7, 5.8, 4.6,
               ["original", "shadow_ray", "sphere_floats", "slots", "combined"],
               [("median (ms)", (807.0, 620.7, 601.1, 719.1, 385.0))],
               [GRAY], point_colors=[GRAY, "7FBFB3", "7FBFB3", "7FBFB3", TEAL], fmt='0" ms"', gap=50)
text(s, 7.1, 6.35, 5.7, 0.6, "Savings overlap: 186 + 206 + 88 ms separately, but combined "
     "385 ms, not 327 (fewer shadow rays also means fewer Vectors to speed up).", size=12, color=MUTED)
notes(s, "Three changes, each aimed at one bottleneck from the flame graph. Build the shadow ray "
         "once: 1.30x. Compute the sphere intersection with plain floats: 1.34x. __slots__ removes "
         "the per-object dictionary: 1.12x. Together 2.10x. They do not simply add up, because "
         "they overlap: once fewer rays are built, there are fewer Vectors for slots to speed up.")

# ============================================================================
# 13. Software results
# ============================================================================
s = new_slide()
title(s, "Software results", num=4,
      sub="pyperformance --rigorous, 120 samples each, same tuned session")
ch = bar_chart(s, 0.5, 1.7, 7.2, 4.9, ["nbody", "raytrace"],
               [("original", (230.4, 807.0)), ("optimized", (144.3, 385.0))],
               [GRAY, TEAL], legend=True, fmt='0.0" ms"', font_size=13, gap=70)
stat(s, 8.2, 1.8, 2.3, "1.60x", "nbody\n37% less time", TEAL, 44, 14)
stat(s, 10.5, 1.8, 2.3, "2.10x", "raytrace\n52% less time", TEAL, 44, 14)
stat(s, 8.2, 3.7, 2.3, "-34%", "nbody\ninstructions", COPPER, 40, 14)
stat(s, 10.5, 3.7, 2.3, "-52%", "raytrace\ninstructions", COPPER, 40, 14)
box_text(s, 8.2, 5.65, 4.5, 1.0, "Target: 7% on two benchmarks.\nBoth outputs bit-identical.",
         fill=CARD, size=15, align=PP_ALIGN.LEFT)
notes(s, "Summary of the software part. Both benchmarks are far above the 7 percent target, and "
         "both produce exactly the same output as before. The counters show why: we execute a "
         "third fewer instructions in nbody and half in raytrace. Cache and branch behaviour "
         "barely changed, which confirms the bottleneck was interpreter work, not memory.")

# ============================================================================
# 14. Why accelerate nbody
# ============================================================================
s = new_slide(dark=True)
title(s, "Why a hardware accelerator, and why nbody", num=5, dark=True,
      sub="What is left after the software fix cannot be removed in Python", )
stat(s, 0.8, 1.9, 3.7, "~100%", "of nbody's time is one loop,\nadvance(): Amdahl is on our side", COPPER, 52, 15, True)
stat(s, 4.8, 1.9, 3.7, "51%", "of the optimized code is float\narithmetic + float objects:\nonly hardware removes that", COPPER, 52, 15, True)
stat(s, 8.8, 1.9, 3.7, "280 B", "of state (5 bodies x 7 doubles):\none transfer in, one out\nper call", COPPER, 52, 15, True)
box(s, 0.8, 4.85, 11.7, 1.8, "22303A")
text(s, 1.1, 4.95, 11.2, 1.65, [
    [("raytrace instead? ", {"bold": True, "color": COPPER}),
     "its math is only ~6% of the time; the cost is Python calls and objects. "
     "A ray-sphere unit would speed up that 6% and leave the rest in Python."],
    [("nbody: ", {"bold": True, "color": COPPER}),
     "the whole advance() loop moves to hardware; 20000 steps run with no software in between."],
], size=16, color="E6EDF3", space_after=8)
notes(s, "Why nbody: the whole benchmark is one loop, so offloading it leaves almost nothing on the "
         "CPU. After our software fix, half of what remains is float arithmetic and float objects, "
         "which no Python rewrite can remove. And the state is tiny, so PCIe is used once per "
         "call. raytrace's math is only 6 percent of its time, so accelerating it would not pay.")

# ============================================================================
# 15. System block diagram
# ============================================================================
s = new_slide()
title(s, "The accelerator in the system", num=5,
      sub="FPGA card on PCIe, 100 MHz, IEEE-754 double precision like Python")
box(s, 0.6, 1.75, 4.1, 5.0, "E7EEF6")
text(s, 0.8, 1.85, 3.7, 0.4, "HOST (CPU)", size=15, bold=True, color=INK)
hb = [("Python benchmark", "advance(dt, n) - unchanged"),
      ("nbody_accel_driver.py", "card? write regs, START, wait,\nread back. No card: software"),
      ("OS: PCIe driver", "mmap BAR0, IOMMU, interrupt")]
for k, (a, b) in enumerate(hb):
    y = 2.35 + k * 1.45
    box_text(s, 0.85, y, 3.6, 1.15, [[(a, {"bold": True})], [(b, {"size": 12, "color": MUTED})]],
             fill=WHITE, line=LINE, size=14)
    if k < 2:
        line(s, 2.65, y + 1.15, 2.65, y + 1.45, INK, 1.5, arrow=True)
line(s, 4.7, 4.25, 5.4, 4.25, COPPER, 6)
text(s, 4.55, 3.7, 1.0, 0.45, "PCIe", size=14, bold=True, color=COPPER, align=PP_ALIGN.CENTER)
box(s, 5.4, 1.75, 7.3, 5.0, "F1F6EE")
text(s, 5.6, 1.85, 6.9, 0.4, "ACCELERATOR CARD (FPGA)", size=15, bold=True, color=INK)
box_text(s, 5.65, 2.35, 2.2, 1.2, [[("PCIe endpoint", {"bold": True})], [("MMIO: addr 16, data 64", {"size": 11, "color": MUTED})]], fill=WHITE, line=LINE, size=13)
box_text(s, 5.65, 3.85, 2.2, 1.55, [[("Registers", {"bold": True})], [("CTRL, STATUS, N,\nSTEPS, DT, CYCLES\n+ body state (16)", {"size": 11, "color": MUTED})]], fill=WHITE, line=LINE, size=13)
box_text(s, 8.25, 2.35, 4.2, 1.2, [[("Controller FSM", {"bold": True})], [("FEED > DRAIN > ACC > POS > next step", {"size": 11, "color": MUTED})]], fill=WHITE, line=LINE, size=13)
box_text(s, 8.25, 3.85, 4.2, 1.2, [[("Pair force pipeline", {"bold": True, "color": WHITE})], [("81 cycles, 1 new pair per cycle", {"size": 11, "color": "D8E0EA"})]], fill=DARK, size=13)
box_text(s, 8.25, 5.3, 4.2, 1.2, [[("Accumulator + position update", {"bold": True})], [("6 adders (pair order) · 3 mul + 3 add", {"size": 11, "color": MUTED})]], fill=WHITE, line=LINE, size=13)
line(s, 6.75, 3.55, 6.75, 3.85, INK, 1.5, arrow=True)
line(s, 7.85, 2.95, 8.25, 2.95, INK, 1.5, arrow=True)
line(s, 7.85, 4.45, 8.25, 4.45, INK, 1.5, arrow=True)
line(s, 10.35, 5.05, 10.35, 5.3, INK, 1.5, arrow=True)
line(s, 8.25, 5.9, 7.85, 5.1, INK, 1.5, arrow=True)
text(s, 5.65, 5.7, 2.4, 0.9, "irq_done -> host\nwhen all steps are done", size=11, color=MUTED)
notes(s, "The host side: the benchmark calls advance exactly as before; the driver writes the "
         "bodies and parameters into the card's registers over PCIe, starts it, waits for the "
         "done interrupt or polls STATUS, and reads the result back. If there is no card it runs "
         "the normal software, so nothing breaks. On the card: registers and body state, a "
         "controller FSM, the pair force pipeline, and the accumulator and position update.")

# ============================================================================
# 16. Pipeline and control
# ============================================================================
s = new_slide()
title(s, "Inside: pair force pipeline and control", num=5,
      sub="Pairs are independent within a step (forces depend only on positions)")
stages = [("S1", "dx,dy,dz", "3 add", 3), ("S2", "squares", "3 mul", 4), ("S3-4", "d2 = sum", "2 add", 6),
          ("S5", "sqrt(d2)", "sqrt", 28), ("S6", "d2 * r", "mul", 4), ("S7", "dt / den", "div", 28),
          ("S8", "m * mag", "2 mul", 4), ("S9", "6 deltas", "6 mul", 4)]
sx = 0.6
total = sum(c for *_, c in stages)
avail = 12.1
for k, (n, op, u, c) in enumerate(stages):
    w = max(1.0, avail * c / total)
    w = min(w, 2.6)
    col = COPPER if c == 28 else DARK
    box_text(s, sx, 1.85, w - 0.08, 1.45, [[(n, {"bold": True, "color": WHITE})],
             [(op, {"size": 12, "color": WHITE})], [(u, {"size": 11, "color": WHITE if c == 28 else "D8E0EA"})],
             [(f"{c} cycles", {"size": 11, "color": WHITE if c == 28 else "D8E0EA"})]],
             fill=col, size=14)
    sx += w
text(s, 0.6, 3.35, 12.1, 0.4, "81 cycles latency · div and sqrt: digit recurrence, 2 bits per stage, "
     "28 stages each · all IEEE-754 double, round to nearest even", size=13, color=MUTED)
fsm = [("IDLE", "wait for START"), ("FEED", "one pair per cycle\ninto the pipeline"),
       ("DRAIN", "wait for the\nlast result"), ("ACC", "apply deltas\nin pair order"),
       ("POS", "update positions\nbody by body"), ("STEP_END", "next step\nor DONE + irq")]
for k, (st, cap) in enumerate(fsm):
    x = 0.8 + k * 2.05
    box_text(s, x, 4.1, 1.6, 0.7, st, fill=CARD, line=LINE, size=15, bold=True, font=MONO)
    if k < len(fsm) - 1:
        line(s, x + 1.6, 4.45, x + 2.05, 4.45, INK, 1.5, arrow=True)
    text(s, x - 0.1, 4.85, 1.8, 0.7, cap, size=12, color=MUTED, align=PP_ALIGN.CENTER,
         space_after=0)
box_text(s, 0.8, 5.7, 11.8, 1.0,
         [[("Measured cycles per step = 6P + 11N + 84", {"bold": True, "font": MONO}),
           ("     benchmark (N = 5, P = 10): 199 cycles = 1.99 µs at 100 MHz", {})]],
         fill=CARD, size=15, align=PP_ALIGN.LEFT)
notes(s, "The pipeline mirrors the software formula stage by stage. A new pair can enter every "
         "cycle, and results come out 81 cycles later; sqrt and divide are the long stages. The "
         "accumulation must follow pair order to be bit-exact, because float addition is not "
         "associative. The cycle formula was measured in simulation for 2, 3, 5 and 16 bodies "
         "and fits exactly: 84 is the pipeline plus control, 6 per pair, 11 per body.")

# ============================================================================
# 17. HW/SW interface
# ============================================================================
s = new_slide()
title(s, "How software talks to it", num=5,
      sub="Memory-mapped registers in PCIe BAR0, 64-bit so one register holds one double")
regs = [("0x0000", "ID", "\"NBODYACC\": driver detects the card"),
        ("0x0008", "CTRL", "bit0 START"),
        ("0x0010", "STATUS", "BUSY, DONE"),
        ("0x0018", "NUM_BODIES", "2 .. 16"),
        ("0x0020", "NUM_STEPS", "steps per call"),
        ("0x0028", "DT", "IEEE-754 double"),
        ("0x0030/38", "STEPS_DONE, CYCLES", "progress, performance counter"),
        ("0x1000+", "BODY[b].f", "x y z vx vy vz m")]
tb = s.shapes.add_table(len(regs) + 1, 3, Inches(0.6), Inches(1.85), Inches(6.9), Inches(4.6)).table
tb.columns[0].width = Inches(1.45)
tb.columns[1].width = Inches(2.35)
tb.columns[2].width = Inches(3.1)
for c, hdr in enumerate(["offset", "register", "meaning"]):
    cell = tb.cell(0, c)
    cell.text = hdr
    cell.fill.solid()
    cell.fill.fore_color.rgb = rgb(DARK)
    p = cell.text_frame.paragraphs[0]
    p.runs[0].font.size = Pt(13); p.runs[0].font.bold = True
    p.runs[0].font.color.rgb = rgb(WHITE); p.runs[0].font.name = BODY
for r, row in enumerate(regs, start=1):
    for c, val in enumerate(row):
        cell = tb.cell(r, c)
        cell.text = val
        cell.fill.solid()
        cell.fill.fore_color.rgb = rgb(CARD if r % 2 else WHITE)
        run = cell.text_frame.paragraphs[0].runs[0]
        run.font.size = Pt(12)
        run.font.name = MONO if c < 2 else BODY
        run.font.color.rgb = rgb(INK)
code(s, 7.9, 1.85, 4.8, 0.85, [
    "advance = accelerated(advance)",
    "advance(0.01, 20000)   # same call",
], size=13)
bullets(s, 7.9, 2.95, 4.8, 3.6, [
    ["card present: write N, steps, dt, 35 body values; START; wait for DONE; read back into the same lists"],
    ["70 register operations per call, independent of the number of steps"],
    ["no card, or > 16 bodies: the normal software advance() runs"],
    ["large systems: one DMA transfer instead of register writes"],
], size=16, space_after=10)
notes(s, "The whole interface is this register map. The driver wraps the benchmark's own "
         "advance function, so the benchmark code does not change: that follows the rule from "
         "the accelerator lecture, keep changes inside a library and never break user code. "
         "Seventy register operations per call, no matter how many steps.")

# ============================================================================
# 18. Verification
# ============================================================================
s = new_slide()
title(s, "Verification: bit for bit", num=5,
      sub="Icarus Verilog simulation, run_tests.sh rebuilds and reruns everything")
v = [("274,014", "floating-point test vectors: add, mul, div, sqrt vs Python's IEEE-754 results, 0 errors"),
     ("4 / 4", "system tests through the registers: real benchmark bodies and 2, 3, 16 bodies, bit-identical"),
     ("20,000", "steps of the real benchmark call: 3,980,000 cycles, all 35 values bit-identical"),
     ("2 / 2", "driver paths: software fallback and offload, both identical")]
for i, (big, lab) in enumerate(v):
    x = 0.7 + i * 3.05
    box(s, x, 1.9, 2.8, 2.9, CARD)
    text(s, x + 0.2, 2.05, 2.5, 0.9, big, size=34, bold=True, color=TEAL, font=HEAD,
         space_after=0, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.2, 3.0, 2.5, 1.7, lab, size=15, color=INK, space_after=0)
box(s, 0.7, 5.15, 11.9, 1.45, DARK)
text(s, 1.0, 5.25, 11.3, 1.25, [
    [("Same results as the software: ", {"bold": True, "color": COPPER}),
     "IEEE double with 1/(d2·sqrt(d2)), because +, -, x, / and sqrt have exactly one correct "
     "IEEE result and pow does not. Bit-identical to the software with the same formula; vs the "
     "original **: 1.3e-9 relative after 20000 steps (rounding only)."]],
    size=15, color="E6EDF3")
notes(s, "We checked the hardware at three levels. Each floating-point unit against Python, bit "
         "for bit, on 274 thousand vectors including cancellation and rounding ties. The whole "
         "accelerator, driven only through its registers like the driver would, against the real "
         "benchmark code, including a full 20000-step call. And the driver in both modes. The only "
         "difference from the original is sqrt instead of pow: same math, rounding-level difference.")

# ============================================================================
# 19. Speedup estimate
# ============================================================================
s = new_slide()
title(s, "Estimated speedup (from measured numbers)", num=5,
      sub="Software: pyperformance medians. Hardware: simulated cycles x 10 ns + PCIe overhead")
bar_chart(s, 0.5, 1.7, 6.3, 4.7, ["original SW", "optimized SW", "accelerator"],
          [("ms per iteration", (232.2, 143.7, 41.0))], [GRAY],
          point_colors=[GRAY, "7FBFB3", COPPER], fmt='0.0" ms"', gap=55, font_size=13)
text(s, 0.7, 6.4, 6.1, 0.6, "accelerator = 20000 x 199 cycles x 10 ns (39.8 ms) + 70 PCIe "
     "accesses at 10 µs + polling (1.2 ms)", size=12, color=MUTED)
stat(s, 7.3, 1.8, 2.6, "5.7x", "vs original software", COPPER, 48, 14)
stat(s, 10.1, 1.8, 2.6, "3.5x", "vs our optimized\nsoftware", COPPER, 48, 14)
box(s, 7.3, 3.9, 5.4, 2.9, CARD)
text(s, 7.55, 4.0, 5.0, 2.8, [
    [("Break-even: ", {"bold": True}), "the PCIe cost is paid once per call, so the card wins above "
     "~125 steps (vs original) or ~230 (vs optimized). The benchmark does 20000."],
    [("More bodies, bigger win: ", {"bold": True}), "1.3x at 2, 3.6x at 5, 5.1x at 8, 6.6x at 16 bodies."],
    [("Assumptions: ", {"bold": True}), "100 MHz reached (not synthesized), 10 µs per register "
     "access (pessimistic), FPGA configured once."],
], size=14, space_after=8)
notes(s, "The estimate uses only measured numbers: the software times from pyperformance and the "
         "cycle count from simulation. 41 milliseconds per iteration instead of 232: 5.7 times "
         "faster than the original, 3.5 times faster than our optimized Python. The overhead is "
         "paid per call, not per step, so the card only pays off with many steps per call.")

# ============================================================================
# 20. Trade-offs
# ============================================================================
s = new_slide()
title(s, "Design trade-offs", num=5, sub="Performance, area, frequency and power")
tos = [("IEEE double vs fixed point", "Exact same results as the software. Fixed point is smaller and "
        "uses less power, but drifts over 20000 steps."),
       ("Div/sqrt: bits per stage", "2 bits at 100 MHz is our balance. 1 bit: ~150 MHz, 2x registers, "
        "more power. 4 bits: smaller, but ~50 MHz."),
       ("Accumulation order", "Must follow pair order to stay exact: float addition is not "
        "associative."),
       ("Parallelism vs area", "Parallel position update: -20% cycles for 5x that area. A second "
        "pipeline: latency, not throughput, is the limit."),
       ("MMIO vs DMA", "Registers for small systems (70 accesses). DMA of one buffer for large "
        "systems, with IOMMU setup."),
       ("Power and energy", "CPU busy 232 ms vs card done in 41 ms: energy per run drops, if the "
        "FPGA is configured once and stays ready.")]
for i, (t, d) in enumerate(tos):
    x = 0.6 + (i % 3) * 4.1
    y = 1.8 + (i // 3) * 2.55
    box(s, x, y, 3.85, 2.3, CARD)
    circle(s, x + 0.2, y + 0.22, 0.42, COPPER, "", 10)
    text(s, x + 0.75, y + 0.15, 3.0, 0.6, t, size=16, bold=True, font=HEAD, space_after=0,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.2, y + 0.85, 3.5, 1.4, d, size=15, color=INK, space_after=0)
notes(s, "Our trade-off analysis. Be ready to defend each one: why double and not fixed point "
         "(exactness), why 2 bits per stage (balance of clock, registers and power), why the "
         "accumulation is sequential (associativity), why not more parallel hardware (latency "
         "dominates), MMIO versus DMA, and the energy argument with its assumption.")

# ============================================================================
# 21. Conclusion
# ============================================================================
s = new_slide(dark=True)
title(s, "Conclusions", dark=True)
lessons = [("Measure before you trust", "Tuned VM, 120 samples, medians: the noise was bigger than the target at first."),
           ("Python's cost is the interpreter", "Not the math: list access, calls, objects, dictionaries."),
           ("Profile, then change one thing", "Every fix came from a flame graph, and the profile even predicted the one that failed."),
           ("Offload the whole loop", "Hardware wins on big batches: 20000 steps per PCIe round trip.")]
for i, (t, d) in enumerate(lessons):
    y = 1.5 + i * 1.3
    circle(s, 0.8, y + 0.1, 0.6, COPPER, str(i + 1), 16)
    text(s, 1.7, y, 6.0, 0.5, t, size=20, bold=True, font=HEAD, color=WHITE, space_after=0)
    text(s, 1.7, y + 0.5, 6.0, 0.7, d, size=14, color="C9D3DE", space_after=0)
stat(s, 8.6, 1.6, 4.0, "1.60x / 2.10x", "software: nbody / raytrace,\nidentical outputs", COPPER, 40, 14, True)
stat(s, 8.6, 3.5, 4.0, "5.7x", "nbody accelerator (estimate),\nverified bit for bit in simulation", COPPER, 40, 14, True)
text(s, 8.6, 5.5, 4.0, 1.0, "Thank you. Questions?", size=24, bold=True, font=HEAD, color=WHITE)
notes(s, "Four take-aways. Close with the numbers and invite questions.")

# ============================================================================
# 22. Demo / reproduce
# ============================================================================
s = new_slide()
title(s, "Demo: everything is reproducible", sub="All in the Git repository")
code(s, 0.7, 1.8, 7.4, 4.3, [
    "# software: setup, verify, profile, benchmark, compare",
    "sudo ./script_nbody.sh",
    "sudo ./script_raytrace.sh",
    "sudo SKIP_SETUP=1 FAST=1 ./script_nbody.sh   # quick",
    "",
    "# correctness only",
    "python3 nbody/verify_nbody.py",
    "python3 raytrace/verify_raytrace.py",
    "",
    "# hardware: FP units, accelerator, driver",
    "hw/nbody_accel/run_tests.sh",
    "python3 hw/nbody_accel/model/estimate_speedup.py",
], size=14)
bullets(s, 8.5, 1.8, 4.2, 4.9, [
    [("Reports: ", {"bold": True}), "report_nbody.txt, report_raytrace.txt"],
    [("Flame graphs: ", {"bold": True}), "results/profiling/<bench>/<version>/"],
    [("Raw timings: ", {"bold": True}), "results/*.json + commands"],
    [("Hardware: ", {"bold": True}), "hw/nbody_accel/ (docs, rtl, tb, sw)"],
    [("AI prompts: ", {"bold": True}), "prompt.txt"],
], size=15, space_after=10)
notes(s, "Backup slide for the live demo. Good quick demos: verify_nbody.py (seconds), "
         "run_tests.sh (about 3 minutes, shows the bit-exact hardware tests and cycle counts), "
         "and opening a py-spy flame graph SVG in the browser.")

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))

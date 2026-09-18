"""Host driver for the nbody force accelerator.

Software interface (see docs/design.md, "Software side"):

    import nbody_accel_driver as accel
    advance = accel.accelerated(software_advance)
    advance(0.01, 20000, bodies, pairs)        # same call as the benchmark

- If an accelerator is present, the driver writes N, NUM_STEPS, DT and the
  body state to the device registers (PCIe BAR0), sets START, waits for DONE
  and reads the new state back into the Python lists in place.
- If no device is present (or the system is larger than the device supports),
  the original software function runs unchanged. The benchmark never breaks,
  and the only software change is inside this library.

Devices:
- PciBarDevice      the real card: memory-maps BAR0 through sysfs
                    (/sys/bus/pci/devices/<BDF>/resource0) and reads/writes
                    64-bit registers. Set NBODY_ACCEL_BDF=0000:01:00.0 to use it.
- RegisterModelDevice
                    a software model of the register map and of the
                    accelerator's arithmetic (same operation order as the RTL).
                    Used to test this driver without hardware.
"""
import math
import mmap
import os
import struct
import time

# Register map (64-bit registers, byte offsets in BAR0)
REG_ID = 0x0000
REG_CTRL = 0x0008
REG_STATUS = 0x0010
REG_NUM_BODIES = 0x0018
REG_NUM_STEPS = 0x0020
REG_DT = 0x0028
REG_STEPS_DONE = 0x0030
REG_CYCLES = 0x0038
BODY_BASE = 0x1000
BODY_STRIDE = 0x40
FIELDS = ("x", "y", "z", "vx", "vy", "vz", "m")

ID_VALUE = 0x4E424F4459414343          # "NBODYACC"
CTRL_START = 1
STATUS_BUSY = 1
STATUS_DONE = 2
MAX_BODIES = 16


def double_to_u64(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def u64_to_double(v):
    return struct.unpack("<d", struct.pack("<Q", v))[0]


def body_reg(b, f):
    return BODY_BASE + BODY_STRIDE * b + 8 * f


class PciBarDevice:
    """Accelerator on PCIe: BAR0 memory-mapped through sysfs."""

    BAR0_SIZE = 0x2000

    def __init__(self, bdf):
        path = f"/sys/bus/pci/devices/{bdf}/resource0"
        self._fd = os.open(path, os.O_RDWR | os.O_SYNC)
        self._mem = mmap.mmap(self._fd, self.BAR0_SIZE, mmap.MAP_SHARED,
                              mmap.PROT_READ | mmap.PROT_WRITE)

    def read64(self, off):
        return struct.unpack_from("<Q", self._mem, off)[0]

    def write64(self, off, value):
        struct.pack_into("<Q", self._mem, off, value & 0xFFFFFFFFFFFFFFFF)

    def close(self):
        self._mem.close()
        os.close(self._fd)


class RegisterModelDevice:
    """Software model of the accelerator's registers and computation.

    The run happens when START is written; STATUS reports DONE afterwards.
    The arithmetic follows the RTL's operation order exactly.
    """

    def __init__(self):
        self.regs = {REG_ID: ID_VALUE, REG_STATUS: 0, REG_NUM_BODIES: 2,
                     REG_NUM_STEPS: 0, REG_DT: 0, REG_STEPS_DONE: 0, REG_CYCLES: 0}
        self.body = [[0] * 7 for _ in range(MAX_BODIES)]
        self.mmio_ops = 0

    def read64(self, off):
        self.mmio_ops += 1
        if off >= BODY_BASE:
            b, rest = divmod(off - BODY_BASE, BODY_STRIDE)
            return self.body[b][rest // 8]
        return self.regs.get(off, 0)

    def write64(self, off, value):
        self.mmio_ops += 1
        if self.regs[REG_STATUS] & STATUS_BUSY:
            return
        if off >= BODY_BASE:
            b, rest = divmod(off - BODY_BASE, BODY_STRIDE)
            self.body[b][rest // 8] = value
        elif off == REG_CTRL and value & CTRL_START:
            self._run()
        elif off in (REG_NUM_BODIES, REG_NUM_STEPS, REG_DT):
            self.regs[off] = value

    def _run(self):
        n = self.regs[REG_NUM_BODIES]
        steps = self.regs[REG_NUM_STEPS]
        dt = u64_to_double(self.regs[REG_DT])
        s = [[u64_to_double(v) for v in self.body[b]] for b in range(n)]
        pairs = [(i, j) for i in range(n - 1) for j in range(i + 1, n)]
        for _ in range(steps):
            for i, j in pairs:
                bi, bj = s[i], s[j]
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
            for b in s:
                b[0] += dt * b[3]
                b[1] += dt * b[4]
                b[2] += dt * b[5]
        for b in range(n):
            self.body[b] = [double_to_u64(v) for v in s[b]]
        self.regs[REG_STEPS_DONE] = steps
        self.regs[REG_STATUS] = STATUS_DONE


def open_device():
    """Return the accelerator device, or None if there is none."""
    bdf = os.environ.get("NBODY_ACCEL_BDF")
    if not bdf:
        return None
    try:
        dev = PciBarDevice(bdf)
    except OSError:
        return None
    if dev.read64(REG_ID) != ID_VALUE:
        dev.close()
        return None
    return dev


def run_on_device(dev, dt, n, bodies, poll_interval=0.0005):
    """Offload n steps. bodies: sequence of (position list, velocity list, mass)."""
    nb = len(bodies)
    dev.write64(REG_NUM_BODIES, nb)
    dev.write64(REG_NUM_STEPS, n)
    dev.write64(REG_DT, double_to_u64(dt))
    for b, (r, v, m) in enumerate(bodies):
        for f, value in enumerate((r[0], r[1], r[2], v[0], v[1], v[2], m)):
            dev.write64(body_reg(b, f), double_to_u64(value))

    dev.write64(REG_CTRL, CTRL_START)
    while not dev.read64(REG_STATUS) & STATUS_DONE:
        time.sleep(poll_interval)          # or wait for the irq_done interrupt

    # write results back into the caller's lists (in place, like advance())
    for b, (r, v, m) in enumerate(bodies):
        vals = [u64_to_double(dev.read64(body_reg(b, f))) for f in range(6)]
        r[0], r[1], r[2] = vals[0], vals[1], vals[2]
        v[0], v[1], v[2] = vals[3], vals[4], vals[5]


def accelerated(software_advance, device=None):
    """Wrap the benchmark's advance(dt, n, bodies, pairs) function.

    Uses the accelerator when available, otherwise the software function.
    """
    dev = device if device is not None else open_device()

    def advance(dt, n, bodies=None, pairs=None):
        if bodies is None:
            bodies = software_advance.__defaults__[0]
        if pairs is None:
            pairs = software_advance.__defaults__[1]
        if dev is None or not (2 <= len(bodies) <= MAX_BODIES) or n <= 0:
            return software_advance(dt, n, bodies, pairs)
        run_on_device(dev, dt, n, bodies)

    advance.device = dev
    return advance

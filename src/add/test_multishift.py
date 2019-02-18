from random import randint
from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from fpbase import MultiShift, MultiShiftR

class MultiShiftModL:
    def __init__(self, width):
        self.ms = MultiShift(width)
        self.a = Signal(width)
        self.b = Signal(self.ms.smax)
        self.x = Signal(width)

    def get_fragment(self, platform=None):

        m = Module()
        m.d.comb += self.x.eq(self.ms.lshift(self.a, self.b))

        return m

class MultiShiftModR:
    def __init__(self, width):
        self.ms = MultiShift(width)
        self.a = Signal(width)
        self.b = Signal(self.ms.smax)
        self.x = Signal(width)

    def get_fragment(self, platform=None):

        m = Module()
        m.d.comb += self.x.eq(self.ms.rshift(self.a, self.b))

        return m

class MultiShiftModRMod:
    def __init__(self, width):
        self.ms = MultiShiftR(width)
        self.a = Signal(width)
        self.b = Signal(self.ms.smax)
        self.x = Signal(width)

    def get_fragment(self, platform=None):

        m = Module()
        m.submodules += self.ms
        m.d.comb += self.ms.i.eq(self.a)
        m.d.comb += self.ms.s.eq(self.b)
        m.d.comb += self.x.eq(self.ms.o)

        return m

def check_case(dut, width, a, b):
    yield dut.a.eq(a)
    yield dut.b.eq(b)
    yield

    x = (a << b) & ((1<<width)-1)

    out_x = yield dut.x
    assert out_x == x, "Output x 0x%x not equal to expected 0x%x" % (out_x, x)

def check_caser(dut, width, a, b):
    yield dut.a.eq(a)
    yield dut.b.eq(b)
    yield

    x = (a >> b) & ((1<<width)-1)

    out_x = yield dut.x
    assert out_x == x, "Output x 0x%x not equal to expected 0x%x" % (out_x, x)

def testbench(dut):
    for i in range(32):
        for j in range(1000):
            a = randint(0, (1<<32)-1)
            yield from check_case(dut, 32, a, i)

def testbenchr(dut):
    for i in range(32):
        for j in range(1000):
            a = randint(0, (1<<32)-1)
            yield from check_caser(dut, 32, a, i)

if __name__ == '__main__':
    dut = MultiShiftModRMod(width=32)
    run_simulation(dut, testbenchr(dut), vcd_name="test_multishift.vcd")

    dut = MultiShiftModR(width=32)
    run_simulation(dut, testbenchr(dut), vcd_name="test_multishift.vcd")

    dut = MultiShiftModL(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_multishift.vcd")


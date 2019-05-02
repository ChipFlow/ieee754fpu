from random import randint
from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from ieee754.fpcommon.fpbase import FPNum

class FPNumModShiftMulti:
    def __init__(self, width):
        self.a = FPNum(width)
        self.ediff = Signal((self.a.e_width, True))

    def elaborate(self, platform=None):

        m = Module()
        #m.d.sync += self.a.decode(self.a.v)
        m.d.sync += self.a.shift_down_multi(self.ediff)

        return m

def check_case(dut, width, e_width, m, e, i):
    yield dut.a.m.eq(m)
    yield dut.a.e.eq(e)
    yield dut.ediff.eq(i)
    yield
    yield

    out_m = yield dut.a.m
    out_e = yield dut.a.e
    ed = yield dut.ediff
    calc_e = (e + i) 
    print (e, bin(m), out_e, calc_e, bin(out_m), i, ed)

    calc_m = ((m >> (i+1)) << 1) | (m & 1)
    for l in range(i):
        if m & (1<<(l+1)):
            calc_m |= 1

    assert out_e == calc_e, "Output e 0x%x != expected 0x%x" % (out_e, calc_e)
    assert out_m == calc_m, "Output m 0x%x != expected 0x%x" % (out_m, calc_m)

def testbench(dut):
    m_width = dut.a.m_width
    e_width = dut.a.e_width
    e_max = dut.a.e_max
    for j in range(200):
        m = randint(0, (1<<m_width)-1)
        zeros = randint(0, 31)
        for i in range(zeros):
            m &= ~(1<<i)
        e = randint(-e_max, e_max)
        for i in range(32):
            yield from check_case(dut, m_width, e_width, m, e, i)

if __name__ == '__main__':
    dut = FPNumModShiftMulti(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_multishift.vcd")

    #dut = MultiShiftModL(width=32)
    #run_simulation(dut, testbench(dut), vcd_name="test_multishift.vcd")


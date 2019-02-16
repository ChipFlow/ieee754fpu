from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from nmigen_div_experiment import FPDIV

class ORGate:
    def __init__(self):
        self.a = Signal()
        self.b = Signal()
        self.x = Signal()

    def get_fragment(self, platform=None):

        m = Module()
        m.d.comb += self.x.eq(self.a | self.b)

        return m

def check_case(dut, a, b, z):
    yield dut.in_a.v.eq(a)
    yield dut.in_a.stb.eq(1)
    yield
    yield
    a_ack = (yield dut.in_a.ack)
    assert a_ack == 0
    yield dut.in_b.v.eq(b)
    yield dut.in_b.stb.eq(1)
    b_ack = (yield dut.in_b.ack)
    assert b_ack == 0

    while True:
        yield
        out_z_stb = (yield dut.out_z.stb)
        if not out_z_stb:
            continue
        yield dut.in_a.stb.eq(0)
        yield dut.in_b.stb.eq(0)
        yield dut.out_z.ack.eq(1)
        yield
        yield dut.out_z.ack.eq(0)
        yield
        yield
        break

    out_z = yield dut.out_z.v
    assert out_z == z, "Output z 0x%x not equal to expected 0x%x" % (out_z, z)

def testbench(dut):
    yield from check_case(dut, 0x40000000, 0x3F800000, 0x40000000)

if __name__ == '__main__':
    dut = FPDIV(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_add.vcd")


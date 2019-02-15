from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from nmigen_add_experiment import FPADD

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
    yield dut.in_a.eq(a)
    yield dut.in_a_stb.eq(1)
    yield
    yield
    a_ack = (yield dut.in_a_ack)
    assert a_ack == 0
    yield dut.in_b.eq(b)
    yield dut.in_b_stb.eq(1)
    b_ack = (yield dut.in_b_ack)
    assert b_ack == 0

    while True:
        yield
        out_z_stb = (yield dut.out_z_stb)
        if not out_z_stb:
            continue
        yield dut.in_a_stb.eq(0)
        yield dut.in_b_stb.eq(0)
        yield dut.out_z_ack.eq(1)
        yield
        yield dut.out_z_ack.eq(0)
        yield
        yield
        break

    out_z = yield dut.out_z
    assert out_z == z, "Output z 0x%x not equal to expected 0x%x" % (out_z, z)

def testbench(dut):
    yield from check_case(dut, 0, 0, 0)
    yield from check_case(dut, 0x3F800000, 0x40000000, 0x40400000)
    #yield from check_case(dut, 1, 0, 1)
    #yield from check_case(dut, 1, 1, 1)

if __name__ == '__main__':
    dut = FPADD(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_add.vcd")


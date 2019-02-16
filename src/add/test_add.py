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
    yield from check_case(dut, 0, 0, 0)
    yield from check_case(dut, 0x3F800000, 0x40000000, 0x40400000)
    yield from check_case(dut, 0x40000000, 0x3F800000, 0x40400000)
    yield from check_case(dut, 0x447A0000, 0x4488B000, 0x4502D800)
    yield from check_case(dut, 0x463B800A, 0x42BA8A3D, 0x463CF51E)
    yield from check_case(dut, 0x42BA8A3D, 0x463B800A, 0x463CF51E)
    yield from check_case(dut, 0x463B800A, 0xC2BA8A3D, 0x463A0AF6)
    yield from check_case(dut, 0xC2BA8A3D, 0x463B800A, 0x463A0AF6)
    yield from check_case(dut, 0xC63B800A, 0x42BA8A3D, 0xC63A0AF6)
    yield from check_case(dut, 0x42BA8A3D, 0xC63B800A, 0xC63A0AF6)
    yield from check_case(dut, 0xFFFFFFFF, 0xC63B800A, 0xFFC00000)
    yield from check_case(dut, 0x7F800000, 0x00000000, 0x7F800000)
    yield from check_case(dut, 0x00000000, 0x7F800000, 0x7F800000)
    yield from check_case(dut, 0xFF800000, 0x00000000, 0xFF800000)
    yield from check_case(dut, 0x00000000, 0xFF800000, 0xFF800000)
    yield from check_case(dut, 0x7F800000, 0x7F800000, 0x7F800000)
    yield from check_case(dut, 0xFF800000, 0xFF800000, 0xFF800000)
    yield from check_case(dut, 0x7F800000, 0xFF800000, 0xFFC00000)
    yield from check_case(dut, 0xFF800000, 0x7F800000, 0x7FC00000)
    yield from check_case(dut, 0x00018643, 0x00FA72A4, 0x00FBF8E7)
    yield from check_case(dut, 0x001A2239, 0x00FA72A4, 0x010A4A6E)
    yield from check_case(dut, 0x3F7FFFFE, 0x3F7FFFFE, 0x3FFFFFFE)
    yield from check_case(dut, 0x7EFFFFEE, 0x7EFFFFEE, 0x7F7FFFEE)
    yield from check_case(dut, 0x7F7FFFEE, 0xFEFFFFEE, 0x7EFFFFEE)
    yield from check_case(dut, 0x7F7FFFEE, 0x756CA884, 0x7F7FFFFD)
    yield from check_case(dut, 0x7F7FFFEE, 0x758A0CF8, 0x7F7FFFFF)
    #yield from check_case(dut, 1, 0, 1)
    #yield from check_case(dut, 1, 1, 1)

if __name__ == '__main__':
    dut = FPADD(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_add.vcd")


from random import randint
from operator import add

from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation

from nmigen_add_experiment import FPADDBase, FPADDBaseMod

def get_case(dut, a, b, mid):
    yield dut.in_mid.eq(mid)
    yield dut.in_a.eq(a)
    yield dut.in_b.eq(b)
    yield dut.in_t.stb.eq(1)
    yield
    yield
    yield
    yield
    ack = (yield dut.in_t.ack)
    assert ack == 0

    yield dut.in_t.stb.eq(0)

    yield dut.out_z.ack.eq(1)

    while True:
        out_z_stb = (yield dut.out_z.stb)
        if not out_z_stb:
            yield
            continue
        out_z = yield dut.out_z.v
        out_mid = yield dut.out_mid
        yield dut.out_z.ack.eq(0)
        yield
        break

    return out_z, out_mid

def check_case(dut, a, b, z, mid=None):
    if mid is None:
        mid = randint(0, 6)
    out_z, out_mid = yield from get_case(dut, a, b, mid)
    assert out_z == z, "Output z 0x%x not equal to expected 0x%x" % (out_z, z)
    assert out_mid == mid, "Output mid 0x%x != expected 0x%x" % (out_mid, mid)



def testbench(dut):
    yield from check_case(dut, 0x36093399, 0x7f6a12f1, 0x7f6a12f1)
    yield from check_case(dut, 0x006CE3EE, 0x806CE3EC, 0x00000002)
    yield from check_case(dut, 0x00000047, 0x80000048, 0x80000001)
    yield from check_case(dut, 0x000116C2, 0x8001170A, 0x80000048)
    yield from check_case(dut, 0x7ed01f25, 0xff559e2c, 0xfedb1d33)
    yield from check_case(dut, 0, 0, 0)
    yield from check_case(dut, 0xFFFFFFFF, 0xC63B800A, 0x7FC00000)
    yield from check_case(dut, 0xFF800000, 0x7F800000, 0x7FC00000)
    #yield from check_case(dut, 0xFF800000, 0x7F800000, 0x7FC00000)
    yield from check_case(dut, 0x7F800000, 0xFF800000, 0x7FC00000)
    yield from check_case(dut, 0x42540000, 0xC2540000, 0x00000000)
    yield from check_case(dut, 0xC2540000, 0x42540000, 0x00000000)
    yield from check_case(dut, 0xfe34f995, 0xff5d59ad, 0xff800000)
    yield from check_case(dut, 0x82471f51, 0x243985f, 0x801c3790)
    yield from check_case(dut, 0x40000000, 0xc0000000, 0x00000000)
    yield from check_case(dut, 0x3F800000, 0x40000000, 0x40400000)
    yield from check_case(dut, 0x40000000, 0x3F800000, 0x40400000)
    yield from check_case(dut, 0x447A0000, 0x4488B000, 0x4502D800)
    yield from check_case(dut, 0x463B800A, 0x42BA8A3D, 0x463CF51E)
    yield from check_case(dut, 0x42BA8A3D, 0x463B800A, 0x463CF51E)
    yield from check_case(dut, 0x463B800A, 0xC2BA8A3D, 0x463A0AF6)
    yield from check_case(dut, 0xC2BA8A3D, 0x463B800A, 0x463A0AF6)
    yield from check_case(dut, 0xC63B800A, 0x42BA8A3D, 0xC63A0AF6)
    yield from check_case(dut, 0x42BA8A3D, 0xC63B800A, 0xC63A0AF6)
    yield from check_case(dut, 0x7F800000, 0x00000000, 0x7F800000)
    yield from check_case(dut, 0x00000000, 0x7F800000, 0x7F800000)
    yield from check_case(dut, 0xFF800000, 0x00000000, 0xFF800000)
    yield from check_case(dut, 0x00000000, 0xFF800000, 0xFF800000)
    yield from check_case(dut, 0x7F800000, 0x7F800000, 0x7F800000)
    yield from check_case(dut, 0xFF800000, 0xFF800000, 0xFF800000)
    yield from check_case(dut, 0xFF800000, 0x7F800000, 0x7FC00000)
    yield from check_case(dut, 0x00018643, 0x00FA72A4, 0x00FBF8E7)
    yield from check_case(dut, 0x001A2239, 0x00FA72A4, 0x010A4A6E)
    yield from check_case(dut, 0x3F7FFFFE, 0x3F7FFFFE, 0x3FFFFFFE)
    yield from check_case(dut, 0x7EFFFFEE, 0x7EFFFFEE, 0x7F7FFFEE)
    yield from check_case(dut, 0x7F7FFFEE, 0xFEFFFFEE, 0x7EFFFFEE)
    yield from check_case(dut, 0x7F7FFFEE, 0x756CA884, 0x7F7FFFFD)
    yield from check_case(dut, 0x7F7FFFEE, 0x758A0CF8, 0x7F7FFFFF)
    yield from check_case(dut, 0x42500000, 0x51A7A358, 0x51A7A358)
    yield from check_case(dut, 0x51A7A358, 0x42500000, 0x51A7A358)
    yield from check_case(dut, 0x4E5693A4, 0x42500000, 0x4E5693A5)
    yield from check_case(dut, 0x42500000, 0x4E5693A4, 0x4E5693A5)

if __name__ == '__main__':
    dut = FPADDBaseMod(width=32, id_wid=5, single_cycle=True)
    run_simulation(dut, testbench(dut), vcd_name="test_add.vcd")


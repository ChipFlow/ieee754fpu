from sfpy import Float32
from nmigen.compat.sim import run_simulation
from dual_add_experiment import ALU


def get_case(dut, a, b, c):
    yield dut.c.v.eq(c)
    yield dut.c.stb.eq(1)
    yield
    yield
    c_ack = (yield dut.c.ack)
    assert c_ack == 0

    yield dut.a.v.eq(a)
    yield dut.a.stb.eq(1)
    yield
    yield
    a_ack = (yield dut.a.ack)
    assert a_ack == 0

    yield dut.b.v.eq(b)
    yield dut.b.stb.eq(1)
    b_ack = (yield dut.b.ack)
    assert b_ack == 0

    while True:
        yield
        out_z_stb = (yield dut.z.stb)
        if not out_z_stb:
            continue
        yield dut.a.stb.eq(0)
        yield dut.b.stb.eq(0)
        yield dut.c.stb.eq(0)
        yield dut.z.ack.eq(1)
        yield
        yield dut.z.ack.eq(0)
        yield
        yield
        break

    out_z = yield dut.z.v
    return out_z

def check_case(dut, a, b, c, z):
    out_z = yield from get_case(dut, a, b, c)
    assert out_z == z, "Output z 0x%x not equal to expected 0x%x" % (out_z, z)

def testbench(dut):
    yield from check_case(dut, 0, 0, 0, 0)
    yield from check_case(dut, 0x3F800000, 0x40000000, 0xc0000000, 0x3F800000)

if __name__ == '__main__':
    dut = ALU(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_dual_add.vcd")


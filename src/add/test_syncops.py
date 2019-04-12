from random import randint
from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog

from inputgroup import FPGetSyncOpsMod


def testbench(dut):
    stb = yield dut.stb
    assert stb == 0
    ack = yield dut.ack
    assert ack == 0

    yield dut.in_op[0].eq(5)
    yield dut.stb.eq(0b01)
    yield dut.ack.eq(1)
    yield
    yield
    decode = yield dut.out_decode
    assert decode == 0

    op0 = yield dut.out_op[0]
    op1 = yield dut.out_op[1]
    assert op0 == 0 and op1 == 0

    yield dut.in_op[1].eq(6)
    yield dut.stb.eq(0b11)
    yield
    yield

    op0 = yield dut.out_op[0]
    op1 = yield dut.out_op[1]
    assert op0 == 5 and op1 == 6

    yield dut.ack.eq(0)
    yield

    op0 = yield dut.out_op[0]
    op1 = yield dut.out_op[1]
    assert op0 == 0 and op1 == 0

if __name__ == '__main__':
    dut = FPGetSyncOpsMod(width=32)
    run_simulation(dut, testbench(dut), vcd_name="test_getsyncops.vcd")
    vl = verilog.convert(dut, ports=dut.ports())
    with open("test_getsyncops.v", "w") as f:
        f.write(vl)

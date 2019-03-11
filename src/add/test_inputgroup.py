from random import randint
from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog

from nmigen_add_experiment import InputGroup


def testbench(dut):
    stb = yield dut.out_op.stb
    assert stb == 0
    ack = yield dut.out_op.ack
    assert ack == 0

    # set row 1 input 0
    yield dut.rs[1].in_op[0].eq(5)
    yield dut.rs[1].stb.eq(0b01) # strobe indicate 1st op ready
    yield dut.rs[1].ack.eq(1)
    yield
    yield

    # check row 1 output (should be inactive)
    decode = yield dut.rs[1].out_decode
    assert decode == 0
    op0 = yield dut.rs[1].out_op[0]
    op1 = yield dut.rs[1].out_op[1]
    assert op0 == 0 and op1 == 0

    # output should be inactive
    out_stb = yield dut.out_op.stb
    assert out_stb == 0

    # set row 0 input 1
    yield dut.rs[1].in_op[1].eq(6)
    yield dut.rs[1].stb.eq(0b11) # strobe indicate both ops ready
    yield
    yield

    # row 0 output should be active
    decode = yield dut.rs[1].out_decode
    assert decode == 1
    op0 = yield dut.rs[1].out_op[0]
    op1 = yield dut.rs[1].out_op[1]
    assert op0 == 5 and op1 == 6

    # output should be active, MID should be 0 until "ack" is set
    out_stb = yield dut.out_op.stb
    assert out_stb == 1
    out_mid = yield dut.mid
    assert out_mid == 0

    yield dut.out_op.ack.eq(1)
    yield
    yield
    yield
    yield

    op0 = yield dut.out_op.v[0]
    op1 = yield dut.out_op.v[1]
    assert op0 == 5 and op1 == 6


if __name__ == '__main__':
    dut = InputGroup(width=32)
    vl = verilog.convert(dut, ports=dut.ports())
    with open("test_inputgroup.v", "w") as f:
        f.write(vl)
    run_simulation(dut, testbench(dut), vcd_name="test_inputgroup.vcd")

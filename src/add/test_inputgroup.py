from random import randint
from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

from nmigen_add_experiment import InputGroup


def testbench(dut):
    stb = yield dut.out_op.stb
    assert stb == 0
    ack = yield dut.out_op.ack
    assert ack == 0

    # set row 1 input 0
    yield dut.rs[1].in_op[0].eq(5)
    yield dut.rs[1].stb.eq(0b01) # strobe indicate 1st op ready
    #yield dut.rs[1].ack.eq(1)
    yield

    # check row 1 output (should be inactive)
    decode = yield dut.rs[1].out_decode
    assert decode == 0
    if False:
        op0 = yield dut.rs[1].out_op[0]
        op1 = yield dut.rs[1].out_op[1]
        assert op0 == 0 and op1 == 0

    # output should be inactive
    out_stb = yield dut.out_op.stb
    assert out_stb == 1

    # set row 0 input 1
    yield dut.rs[1].in_op[1].eq(6)
    yield dut.rs[1].stb.eq(0b11) # strobe indicate both ops ready

    # set acknowledgement of output... takes 1 cycle to respond
    yield dut.out_op.ack.eq(1)
    yield
    yield dut.out_op.ack.eq(0) # clear ack on output
    yield dut.rs[1].stb.eq(0) # clear row 1 strobe

    # output strobe should be active, MID should be 0 until "ack" is set...
    out_stb = yield dut.out_op.stb
    assert out_stb == 1
    out_mid = yield dut.mid
    assert out_mid == 0

    # ... and output should not yet be passed through either
    op0 = yield dut.out_op.v[0]
    op1 = yield dut.out_op.v[1]
    assert op0 == 0 and op1 == 0

    # wait for out_op.ack to activate...
    yield dut.rs[1].stb.eq(0b00) # set row 1 strobes to zero
    yield

    # *now* output should be passed through
    op0 = yield dut.out_op.v[0]
    op1 = yield dut.out_op.v[1]
    assert op0 == 5 and op1 == 6

    # set row 2 input
    yield dut.rs[2].in_op[0].eq(3)
    yield dut.rs[2].in_op[1].eq(4)
    yield dut.rs[2].stb.eq(0b11) # strobe indicate 1st op ready
    yield dut.out_op.ack.eq(1) # set output ack
    yield
    yield dut.rs[2].stb.eq(0) # clear row 2 strobe
    yield dut.out_op.ack.eq(0) # set output ack
    yield
    op0 = yield dut.out_op.v[0]
    op1 = yield dut.out_op.v[1]
    assert op0 == 3 and op1 == 4, "op0 %d op1 %d" % (op0, op1)
    out_mid = yield dut.mid
    assert out_mid == 2

    # set row 0 and 3 input
    yield dut.rs[0].in_op[0].eq(9)
    yield dut.rs[0].in_op[1].eq(8)
    yield dut.rs[0].stb.eq(0b11) # strobe indicate 1st op ready
    yield dut.rs[3].in_op[0].eq(1)
    yield dut.rs[3].in_op[1].eq(2)
    yield dut.rs[3].stb.eq(0b11) # strobe indicate 1st op ready

    # set acknowledgement of output... takes 1 cycle to respond
    yield dut.out_op.ack.eq(1)
    yield
    yield dut.rs[0].stb.eq(0) # clear row 1 strobe
    yield
    out_mid = yield dut.mid
    assert out_mid == 0, "out mid %d" % out_mid

    yield
    yield dut.rs[3].stb.eq(0) # clear row 1 strobe
    yield dut.out_op.ack.eq(0) # clear ack on output
    yield
    out_mid = yield dut.mid
    assert out_mid == 3, "out mid %d" % out_mid


class InputTest:
    def __init__(self, dut):
        self.dut = dut
        self.di = {}
        self.do = {}
        self.tlen = 10
        for mid in range(dut.num_rows):
            self.di[mid] = {}
            self.do[mid] = {}
            for i in range(self.tlen):
                self.di[mid][i] = randint(0, 100)
                self.do[mid][i] = self.di[mid][i]

    def send(self, mid):
        for i in range(self.tlen):
            op2 = self.di[mid][i]
            rs = dut.rs[mid]
            ack = yield rs.ack
            while not ack:
                yield
                ack = yield rs.ack
            yield rs.in_op[0].eq(i)
            yield rs.in_op[1].eq(op2)
            yield rs.stb.eq(0b11) # strobe indicate 1st op ready
            ack = yield rs.ack
            while ack:
                yield
                ack = yield rs.ack
            yield rs.stb.eq(0)

            # wait random period of time before queueing another value
            for i in range(randint(0, 8)):
                yield

    def recv(self):
        while True:
            stb = yield dut.out_op.stb
            yield dut.out_op.ack.eq(0)
            while not stb:
                yield dut.out_op.ack.eq(1)
                yield
                stb = yield dut.out_op.stb

            stb = yield dut.out_op.stb
            while stb:
                yield
                stb = yield dut.out_op.stb
            mid = yield dut.mid
            out_i = yield dut.out_op.v[0]
            out_v = yield dut.out_op.v[1]

            # see if this output has occurred already, delete it if it has
            assert out_i in self.do[mid]
            assert self.do[mid][out_i] == out_v
            del self.do[mid][out_i]

            # check if there's any more outputs
            zerolen = True
            for (k, v) in self.do.items():
                if v:
                    zerolen = False
            if zerolen:
                break

if __name__ == '__main__':
    dut = InputGroup(width=32)
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_inputgroup.il", "w") as f:
        f.write(vl)
    run_simulation(dut, testbench(dut), vcd_name="test_inputgroup.vcd")

    dut = InputGroup(width=16)
    test = InputTest(dut)
    run_simulation(dut, [test.send(3), test.send(2),
                         test.send(1), test.send(0),
                         test.recv()],
                   vcd_name="test_inputgroup_parallel.vcd")


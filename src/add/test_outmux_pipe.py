from random import randint
from math import log
from nmigen import Module, Signal, Cat
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

from multipipe import CombMultiOutPipeline


class MuxUnbufferedPipeline(CombMultiOutPipeline):
    def __init__(self, stage, n_len):
        # HACK: stage is also the n-way multiplexer
        CombMultiOutPipeline.__init__(self, stage, n_len=n_len, n_mux=stage)

        # HACK: n-mux is also the stage... so set the muxid equal to input mid
        stage.m_id = self.p.i_data.mid

    def ports(self):
        return self.p_mux.ports()


class PassInData:
    def __init__(self):
        self.mid = Signal(2, reset_less=True)
        self.data = Signal(16, reset_less=True)

    def eq(self, i):
        return [self.mid.eq(i.mid), self.data.eq(i.data)]

    def ports(self):
        return [self.mid, self.data]


class PassThroughStage:

    def ispec(self):
        return PassInData()

    def ospec(self):
        return Signal(16, name="data_out", reset_less=True)
                
    def process(self, i):
        return i.data



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


class OutputTest:
    def __init__(self, dut):
        self.dut = dut
        self.di = []
        self.do = {}
        self.tlen = 10
        for i in range(self.tlen * dut.num_rows):
            if i < dut.num_rows:
                mid = i
            else:
                mid = randint(0, dut.num_rows-1)
            data = randint(0, 255) + (mid<<8)
            if mid not in self.do:
                self.do[mid] = []
            self.di.append((data, mid))
            self.do[mid].append(data)

    def send(self):
        for i in range(self.tlen * dut.num_rows):
            op2 = self.di[i][0]
            mid = self.di[i][1]
            rs = dut.p
            yield rs.i_valid.eq(1)
            yield rs.i_data.data.eq(op2)
            yield rs.i_data.mid.eq(mid)
            yield
            o_p_ready = yield rs.o_ready
            while not o_p_ready:
                yield
                o_p_ready = yield rs.o_ready

            print ("send", mid, i, hex(op2))

            yield rs.i_valid.eq(0)
            # wait random period of time before queueing another value
            for i in range(randint(0, 3)):
                yield

        yield rs.i_valid.eq(0)

    def rcv(self, mid):
        out_i = 0
        count = 0
        stall_range = randint(0, 3)
        while out_i != len(self.do[mid]):
            count += 1
            assert count != 2000, "timeout: too long"
            n = self.dut.n[mid]
            yield n.i_ready.eq(1)
            yield
            o_n_valid = yield n.o_valid
            i_n_ready = yield n.i_ready
            if not o_n_valid or not i_n_ready:
                continue

            out_v = yield n.o_data

            print ("recv", mid, out_i, hex(out_v))

            assert self.do[mid][out_i] == out_v # pass-through data

            out_i += 1

            if randint(0, 5) == 0:
                stall_range = randint(0, 3)
            stall = randint(0, stall_range) != 0
            if stall:
                yield n.i_ready.eq(0)
                for i in range(stall_range):
                    yield


class TestPriorityMuxPipe(MuxUnbufferedPipeline):
    def __init__(self):
        self.num_rows = 4
        stage = PassThroughStage()
        MuxUnbufferedPipeline.__init__(self, stage, n_len=self.num_rows)

    def ports(self):
        res = [self.p.i_valid, self.p.o_ready] + \
                self.p.i_data.ports()
        for i in range(len(self.n)):
            res += [self.n[i].i_ready, self.n[i].o_valid] + \
                    [self.n[i].o_data]
                    #self.n[i].o_data.ports()
        return res


if __name__ == '__main__':
    dut = TestPriorityMuxPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_outmux_pipe.il", "w") as f:
        f.write(vl)
    #run_simulation(dut, testbench(dut), vcd_name="test_inputgroup.vcd")

    test = OutputTest(dut)
    run_simulation(dut, [test.rcv(1), test.rcv(0),
                         test.rcv(3), test.rcv(2),
                         test.send()],
                   vcd_name="test_outmux_pipe.vcd")


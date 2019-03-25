from random import randint
from math import log
from nmigen import Module, Signal, Cat
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil
from nmigen.lib.coding import PriorityEncoder

from example_buf_pipe import UnbufferedPipeline


class InputPriorityArbiter:
    def __init__(self, pipe, num_rows):
        self.pipe = pipe
        self.num_rows = num_rows
        self.mmax = int(log(self.num_rows) / log(2))
        self.m_id = Signal(self.mmax, reset_less=True) # multiplex id
        self.active = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()

        assert len(self.pipe.p) == self.num_rows, \
                "must declare input to be same size"
        pe = PriorityEncoder(self.num_rows)
        m.submodules.selector = pe

        # connect priority encoder
        in_ready = []
        for i in range(self.num_rows):
            p_i_valid = Signal(reset_less=True)
            m.d.comb += p_i_valid.eq(self.pipe.p[i].i_valid_logic())
            in_ready.append(p_i_valid)
        m.d.comb += pe.i.eq(Cat(*in_ready)) # array of input "valids"
        m.d.comb += self.active.eq(~pe.n)   # encoder active (one input valid)
        m.d.comb += self.m_id.eq(pe.o)       # output one active input

        return m

    def ports(self):
        return [self.m_id, self.active]


class PriorityUnbufferedPipeline(UnbufferedPipeline):
    def __init__(self, stage, p_len=4):
        p_mux = InputPriorityArbiter(self, p_len)
        UnbufferedPipeline.__init__(self, stage, p_len=p_len, p_mux=p_mux)

    def ports(self):
        return self.p_mux.ports()
        #return UnbufferedPipeline.ports(self) + self.p_mux.ports()

class PassData:
    def __init__(self):
        self.mid = Signal(2, reset_less=True)
        self.idx = Signal(6, reset_less=True)
        self.data = Signal(16, reset_less=True)

    def eq(self, i):
        return [self.mid.eq(i.mid), self.idx.eq(i.idx), self.data.eq(i.data)]

    def ports(self):
        return [self.mid, self.idx, self.data]

class PassThroughStage:
    def ispec(self):
        return PassData()
    def ospec(self):
        return self.ispec() # same as ospec
                
    def process(self, i):
        return i # pass-through



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
                self.di[mid][i] = randint(0, 100) + (mid<<8)
                self.do[mid][i] = self.di[mid][i]

    def send(self, mid):
        for i in range(self.tlen):
            op2 = self.di[mid][i]
            rs = dut.p[mid]
            yield rs.i_valid.eq(1)
            yield rs.i_data.data.eq(op2)
            yield rs.i_data.idx.eq(i)
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
        ## wait random period of time before queueing another value
        #for i in range(randint(0, 3)):
        #    yield

        #send_range = randint(0, 3)
        #if send_range == 0:
        #    send = True
        #else:
        #    send = randint(0, send_range) != 0

    def rcv(self):
        while True:
            #stall_range = randint(0, 3)
            #for j in range(randint(1,10)):
            #    stall = randint(0, stall_range) != 0
            #    yield self.dut.n[0].i_ready.eq(stall)
            #    yield
            n = self.dut.n[0]
            yield n.i_ready.eq(1)
            yield
            o_n_valid = yield n.o_valid
            i_n_ready = yield n.i_ready
            if not o_n_valid or not i_n_ready:
                continue

            mid = yield n.o_data.mid
            out_i = yield n.o_data.idx
            out_v = yield n.o_data.data

            print ("recv", mid, out_i, hex(out_v))

            # see if this output has occurred already, delete it if it has
            assert out_i in self.do[mid], "out_i %d not in array %s" % \
                                          (out_i, repr(self.do[mid]))
            assert self.do[mid][out_i] == out_v # pass-through data
            del self.do[mid][out_i]

            # check if there's any more outputs
            zerolen = True
            for (k, v) in self.do.items():
                if v:
                    zerolen = False
            if zerolen:
                break


class TestPriorityMuxPipe(PriorityUnbufferedPipeline):
    def __init__(self):
        self.num_rows = 4
        stage = PassThroughStage()
        PriorityUnbufferedPipeline.__init__(self, stage, p_len=self.num_rows)

    def ports(self):
        res = []
        for i in range(len(self.p)):
            res += [self.p[i].i_valid, self.p[i].o_ready] + \
                    self.p[i].i_data.ports()
        for i in range(len(self.n)):
            res += [self.n[i].i_ready, self.n[i].o_valid] + \
                    self.n[i].o_data.ports()
        return res


if __name__ == '__main__':
    dut = TestPriorityMuxPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_inputgroup.il", "w") as f:
        f.write(vl)
    #run_simulation(dut, testbench(dut), vcd_name="test_inputgroup.vcd")

    test = InputTest(dut)
    run_simulation(dut, [test.send(1), test.send(0),
                         test.send(3), test.send(2),
                         test.rcv()],
                   vcd_name="test_inputgroup_parallel.vcd")


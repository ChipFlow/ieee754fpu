""" key strategic example showing how to do multi-input fan-in into a
    multi-stage pipeline, then multi-output fanout.

    the multiplex ID from the fan-in is passed in to the pipeline, preserved,
    and used as a routing ID on the fanout.
"""

from random import randint
from math import log
from nmigen import Module, Signal, Cat, Value
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

from multipipe import CombMultiOutPipeline, CombMuxOutPipe
from multipipe import PriorityCombMuxInPipe
from singlepipe import UnbufferedPipeline


class PassData: # (Value):
    def __init__(self):
        self.mid = Signal(2, reset_less=True)
        self.idx = Signal(8, reset_less=True)
        self.data = Signal(16, reset_less=True)

    def _rhs_signals(self):
        return self.ports()

    def shape(self):
        bits, sign = 0, False
        for elem_bits, elem_sign in (elem.shape() for elem in self.ports()):
            bits = max(bits, elem_bits + elem_sign)
            sign = max(sign, elem_sign)
        return bits, sign

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



class PassThroughPipe(UnbufferedPipeline):
    def __init__(self):
        UnbufferedPipeline.__init__(self, PassThroughStage())


class InputTest:
    def __init__(self, dut):
        self.dut = dut
        self.di = {}
        self.do = {}
        self.tlen = 100
        for mid in range(dut.num_rows):
            self.di[mid] = {}
            self.do[mid] = {}
            for i in range(self.tlen):
                self.di[mid][i] = randint(0, 255) + (mid<<8)
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
        yield

        print ("send ended", mid)

        ## wait random period of time before queueing another value
        #for i in range(randint(0, 3)):
        #    yield

        #send_range = randint(0, 3)
        #if send_range == 0:
        #    send = True
        #else:
        #    send = randint(0, send_range) != 0

    def rcv(self, mid):
        while True:
            #stall_range = randint(0, 3)
            #for j in range(randint(1,10)):
            #    stall = randint(0, stall_range) != 0
            #    yield self.dut.n[0].i_ready.eq(stall)
            #    yield
            n = self.dut.n[mid]
            yield n.i_ready.eq(1)
            yield
            o_n_valid = yield n.o_valid
            i_n_ready = yield n.i_ready
            if not o_n_valid or not i_n_ready:
                continue

            out_mid = yield n.o_data.mid
            out_i = yield n.o_data.idx
            out_v = yield n.o_data.data

            print ("recv", out_mid, out_i, hex(out_v))

            # see if this output has occurred already, delete it if it has
            assert mid == out_mid, "out_mid %d not correct %d" % (out_mid, mid)
            assert out_i in self.do[mid], "out_i %d not in array %s" % \
                                          (out_i, repr(self.do[mid]))
            assert self.do[mid][out_i] == out_v # pass-through data
            del self.do[mid][out_i]

            # check if there's any more outputs
            if len(self.do[mid]) == 0:
                break
        print ("recv ended", mid)


class TestPriorityMuxPipe(PriorityCombMuxInPipe):
    def __init__(self, num_rows):
        self.num_rows = num_rows
        stage = PassThroughStage()
        PriorityCombMuxInPipe.__init__(self, stage, p_len=self.num_rows)


class OutputTest:
    def __init__(self, dut):
        self.dut = dut
        self.di = []
        self.do = {}
        self.tlen = 100
        for i in range(self.tlen * dut.num_rows):
            if i < dut.num_rows:
                mid = i
            else:
                mid = randint(0, dut.num_rows-1)
            data = randint(0, 255) + (mid<<8)

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


class TestMuxOutPipe(CombMuxOutPipe):
    def __init__(self, num_rows):
        self.num_rows = num_rows
        stage = PassThroughStage()
        CombMuxOutPipe.__init__(self, stage, n_len=self.num_rows)


class TestInOutPipe:
    def __init__(self, num_rows=4):
        self.num_rows = num_rows
        self.inpipe = TestPriorityMuxPipe(num_rows) # fan-in (combinatorial)
        self.pipe1 = PassThroughPipe()              # stage 1 (clock-sync)
        self.pipe2 = PassThroughPipe()              # stage 2 (clock-sync)
        self.outpipe = TestMuxOutPipe(num_rows)     # fan-out (combinatorial)

        self.p = self.inpipe.p  # kinda annoying,
        self.n = self.outpipe.n # use pipe in/out as this class in/out
        self._ports = self.inpipe.ports() + self.outpipe.ports()

    def elaborate(self, platform):
        m = Module()
        m.submodules.inpipe = self.inpipe
        m.submodules.pipe1 = self.pipe1
        m.submodules.pipe2 = self.pipe2
        m.submodules.outpipe = self.outpipe

        m.d.comb += self.inpipe.n.connect_to_next(self.pipe1.p)
        m.d.comb += self.pipe1.connect_to_next(self.pipe2)
        m.d.comb += self.pipe2.connect_to_next(self.outpipe)

        return m

    def ports(self):
        return self._ports


if __name__ == '__main__':
    dut = TestInOutPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_inoutmux_pipe.il", "w") as f:
        f.write(vl)
    #run_simulation(dut, testbench(dut), vcd_name="test_inputgroup.vcd")

    test = InputTest(dut)
    run_simulation(dut, [test.rcv(1), test.rcv(0),
                         test.rcv(3), test.rcv(2),
                         test.send(0), test.send(1),
                         test.send(3), test.send(2),
                        ],
                   vcd_name="test_inoutmux_pipe.vcd")


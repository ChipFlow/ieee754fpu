from random import randint
from math import log
from nmigen import Module, Signal, Cat, Elaboratable
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

from nmutil.multipipe import CombMuxOutPipe
from nmutil.singlepipe import SimpleHandshake, PassThroughHandshake, RecordObject


class PassInData(RecordObject):
    def __init__(self):
        RecordObject.__init__(self)
        self.muxid = Signal(2, reset_less=True)
        self.data = Signal(16, reset_less=True)


class PassThroughStage:

    def ispec(self):
        return PassInData()

    def ospec(self, name):
        return Signal(16, name="%s_dout" % name, reset_less=True)
                
    def process(self, i):
        return i.data


class PassThroughDataStage:
    def ispec(self):
        return PassInData()
    def ospec(self):
        return self.ispec() # same as ospec

    def process(self, i):
        return i # pass-through



class PassThroughPipe(PassThroughHandshake):
    def __init__(self):
        PassThroughHandshake.__init__(self, PassThroughDataStage())


class OutputTest:
    def __init__(self, dut):
        self.dut = dut
        self.di = []
        self.do = {}
        self.tlen = 10
        for i in range(self.tlen * dut.num_rows):
            if i < dut.num_rows:
                muxid = i
            else:
                muxid = randint(0, dut.num_rows-1)
            data = randint(0, 255) + (muxid<<8)
            if muxid not in self.do:
                self.do[muxid] = []
            self.di.append((data, muxid))
            self.do[muxid].append(data)

    def send(self):
        for i in range(self.tlen * self.dut.num_rows):
            op2 = self.di[i][0]
            muxid = self.di[i][1]
            rs = self.dut.p
            yield rs.valid_i.eq(1)
            yield rs.data_i.data.eq(op2)
            yield rs.data_i.muxid.eq(muxid)
            yield
            o_p_ready = yield rs.ready_o
            while not o_p_ready:
                yield
                o_p_ready = yield rs.ready_o

            print ("send", muxid, i, hex(op2))

            yield rs.valid_i.eq(0)
            # wait random period of time before queueing another value
            for i in range(randint(0, 3)):
                yield

        yield rs.valid_i.eq(0)

    def rcv(self, muxid):
        out_i = 0
        count = 0
        stall_range = randint(0, 3)
        while out_i != len(self.do[muxid]):
            count += 1
            assert count != 2000, "timeout: too long"
            n = self.dut.n[muxid]
            yield n.ready_i.eq(1)
            yield
            o_n_valid = yield n.valid_o
            i_n_ready = yield n.ready_i
            if not o_n_valid or not i_n_ready:
                continue

            out_v = yield n.data_o

            print ("recv", muxid, out_i, hex(out_v))

            assert self.do[muxid][out_i] == out_v # pass-through data

            out_i += 1

            if randint(0, 5) == 0:
                stall_range = randint(0, 3)
            stall = randint(0, stall_range) != 0
            if stall:
                yield n.ready_i.eq(0)
                for i in range(stall_range):
                    yield


class TestPriorityMuxPipe(CombMuxOutPipe):
    def __init__(self, num_rows):
        self.num_rows = num_rows
        stage = PassThroughStage()
        CombMuxOutPipe.__init__(self, stage, n_len=self.num_rows)


class TestSyncToPriorityPipe(Elaboratable):
    def __init__(self):
        self.num_rows = 4
        self.pipe = PassThroughPipe()
        self.muxpipe = TestPriorityMuxPipe(self.num_rows)

        self.p = self.pipe.p
        self.n = self.muxpipe.n

    def elaborate(self, platform):
        m = Module()
        m.submodules.pipe = self.pipe
        m.submodules.muxpipe = self.muxpipe
        m.d.comb += self.pipe.n.connect_to_next(self.muxpipe.p)
        return m

    def ports(self):
        res = [self.p.valid_i, self.p.ready_o] + \
                self.p.data_i.ports()
        for i in range(len(self.n)):
            res += [self.n[i].ready_i, self.n[i].valid_o] + \
                    [self.n[i].data_o]
                    #self.n[i].data_o.ports()
        return res


def test1():
    dut = TestSyncToPriorityPipe()
    vl = rtlil.convert(dut, ports=dut.ports())
    with open("test_outmux_pipe.il", "w") as f:
        f.write(vl)

    test = OutputTest(dut)
    run_simulation(dut, [test.rcv(1), test.rcv(0),
                         test.rcv(3), test.rcv(2),
                         test.send()],
                   vcd_name="test_outmux_pipe.vcd")

if __name__ == '__main__':
    test1()

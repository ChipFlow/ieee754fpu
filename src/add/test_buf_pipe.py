from nmigen import Module, Signal
from nmigen.compat.sim import run_simulation
from example_buf_pipe import BufPipe
from random import randint


def check_o_n_stb(dut, val):
    o_n_stb = yield dut.o_n_stb
    assert o_n_stb == val


def testbench(dut):
    #yield dut.i_p_rst.eq(1)
    yield dut.i_n_busy.eq(1)
    yield dut.o_p_busy.eq(1)
    yield
    yield
    #yield dut.i_p_rst.eq(0)
    yield dut.i_n_busy.eq(0)
    yield dut.stage.i_data.eq(5)
    yield dut.i_p_stb.eq(1)
    yield

    yield dut.stage.i_data.eq(7)
    yield from check_o_n_stb(dut, 0) # effects of i_p_stb delayed
    yield
    yield from check_o_n_stb(dut, 1) # ok *now* i_p_stb effect is felt

    yield dut.stage.i_data.eq(2)
    yield
    yield dut.i_n_busy.eq(1) # begin going into "stall" (next stage says busy)
    yield dut.stage.i_data.eq(9)
    yield
    yield dut.i_p_stb.eq(0)
    yield dut.stage.i_data.eq(12)
    yield
    yield dut.stage.i_data.eq(32)
    yield dut.i_n_busy.eq(0)
    yield
    yield from check_o_n_stb(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_stb(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_stb(dut, 0) # buffer outputted, *now* we're done.
    yield


def testbench2(dut):
    #yield dut.i_p_rst.eq(1)
    yield dut.i_n_busy.eq(1)
    #yield dut.o_p_busy.eq(1)
    yield
    yield
    #yield dut.i_p_rst.eq(0)
    yield dut.i_n_busy.eq(0)
    yield dut.i_data.eq(5)
    yield dut.i_p_stb.eq(1)
    yield

    yield dut.i_data.eq(7)
    yield from check_o_n_stb(dut, 0) # effects of i_p_stb delayed 2 clocks
    yield
    yield from check_o_n_stb(dut, 0) # effects of i_p_stb delayed 2 clocks

    yield dut.i_data.eq(2)
    yield
    yield from check_o_n_stb(dut, 1) # ok *now* i_p_stb effect is felt
    yield dut.i_n_busy.eq(1) # begin going into "stall" (next stage says busy)
    yield dut.i_data.eq(9)
    yield
    yield dut.i_p_stb.eq(0)
    yield dut.i_data.eq(12)
    yield
    yield dut.i_data.eq(32)
    yield dut.i_n_busy.eq(0)
    yield
    yield from check_o_n_stb(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_stb(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_stb(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_stb(dut, 0) # buffer outputted, *now* we're done.
    yield
    yield
    yield


def testbench3(dut):
    data = []
    for i in range(10000):
        #data.append(randint(0, 1<<16-1))
        data.append(i+1)
    i = 0
    o = 0
    while True:
        stall = randint(0, 3) == 0
        send = randint(0, 5) != 0
        yield dut.i_n_busy.eq(stall)
        o_p_busy = yield dut.o_p_busy
        if not o_p_busy:
            if send and i != len(data):
                yield dut.i_p_stb.eq(1)
                yield dut.stage.i_data.eq(data[i])
                i += 1
            else:
                yield dut.i_p_stb.eq(0)
        yield
        o_n_stb = yield dut.o_n_stb
        i_n_busy = yield dut.i_n_busy
        if o_n_stb and not i_n_busy:
            o_data = yield dut.stage.o_data
            assert o_data == data[o] + 1, "%d-%d data %x not match %x\n" \
                                        % (i, o, o_data, data[o])
            o += 1
            if o == len(data):
                break


def testbench4(dut):
    data = []
    for i in range(10000):
        #data.append(randint(0, 1<<16-1))
        data.append(i+1)
    i = 0
    o = 0
    while True:
        stall = randint(0, 3) == 0
        send = randint(0, 5) != 0
        yield dut.i_n_busy.eq(stall)
        o_p_busy = yield dut.o_p_busy
        if not o_p_busy:
            if send and i != len(data):
                yield dut.i_p_stb.eq(1)
                yield dut.i_data.eq(data[i])
                i += 1
            else:
                yield dut.i_p_stb.eq(0)
        yield
        o_n_stb = yield dut.o_n_stb
        i_n_busy = yield dut.i_n_busy
        if o_n_stb and not i_n_busy:
            o_data = yield dut.o_data
            assert o_data == data[o] + 2, "%d-%d data %x not match %x\n" \
                                        % (i, o, o_data, data[o])
            o += 1
            if o == len(data):
                break


class BufPipe2:
    """
        connect these:  ------|---------------|
                              v               v
        i_p_stb  >>in  pipe1 o_n_stb  out>> i_p_stb  >>in  pipe2
        o_p_busy <<out pipe1 i_n_busy <<in  o_p_busy <<out pipe2
        stage.i_data   >>in  pipe1 o_data   out>> stage.i_data   >>in  pipe2
    """
    def __init__(self):
        self.pipe1 = BufPipe()
        self.pipe2 = BufPipe()

        # input
        self.i_p_stb = Signal()    # >>in - comes in from PREVIOUS stage
        self.i_n_busy = Signal()   # in<< - comes in from the NEXT stage
        self.i_data = Signal(32) # >>in - comes in from the PREVIOUS stage

        # output
        self.o_n_stb = Signal()    # out>> - goes out to the NEXT stage
        self.o_p_busy = Signal()   # <<out - goes out to the PREVIOUS stage
        self.o_data = Signal(32) # out>> - goes out to the NEXT stage

    def elaborate(self, platform):
        m = Module()
        m.submodules.pipe1 = self.pipe1
        m.submodules.pipe2 = self.pipe2

        # connect inter-pipe input/output stb/busy/data
        m.d.comb += self.pipe2.i_p_stb.eq(self.pipe1.o_n_stb)
        m.d.comb += self.pipe1.i_n_busy.eq(self.pipe2.o_p_busy)
        m.d.comb += self.pipe2.stage.i_data.eq(self.pipe1.stage.o_data)

        # inputs/outputs to the module: pipe1 connections here (LHS)
        m.d.comb += self.pipe1.i_p_stb.eq(self.i_p_stb)
        m.d.comb += self.o_p_busy.eq(self.pipe1.o_p_busy)
        m.d.comb += self.pipe1.stage.i_data.eq(self.i_data)

        # now pipe2 connections (RHS)
        m.d.comb += self.o_n_stb.eq(self.pipe2.o_n_stb)
        m.d.comb += self.pipe2.i_n_busy.eq(self.i_n_busy)
        m.d.comb += self.o_data.eq(self.pipe2.stage.o_data)

        return m

if __name__ == '__main__':
    dut = BufPipe()
    run_simulation(dut, testbench(dut), vcd_name="test_bufpipe.vcd")

    dut = BufPipe2()
    run_simulation(dut, testbench2(dut), vcd_name="test_bufpipe2.vcd")

    dut = BufPipe()
    run_simulation(dut, testbench3(dut), vcd_name="test_bufpipe3.vcd")

    dut = BufPipe2()
    run_simulation(dut, testbench4(dut), vcd_name="test_bufpipe4.vcd")

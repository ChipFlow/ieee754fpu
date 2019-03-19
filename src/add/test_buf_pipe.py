from nmigen import Module, Signal, Mux
from nmigen.compat.sim import run_simulation
from example_buf_pipe import ExampleBufPipe, ExampleBufPipeAdd
from example_buf_pipe import ExampleCombPipe, CombPipe
from example_buf_pipe import PrevControl, NextControl
from random import randint


def check_o_n_valid(dut, val):
    o_n_valid = yield dut.n.o_valid
    assert o_n_valid == val


def testbench(dut):
    #yield dut.i_p_rst.eq(1)
    yield dut.n.i_ready.eq(0)
    yield dut.p.o_ready.eq(0)
    yield
    yield
    #yield dut.i_p_rst.eq(0)
    yield dut.n.i_ready.eq(1)
    yield dut.p.i_data.eq(5)
    yield dut.p.i_valid.eq(1)
    yield

    yield dut.p.i_data.eq(7)
    yield from check_o_n_valid(dut, 0) # effects of i_p_valid delayed
    yield
    yield from check_o_n_valid(dut, 1) # ok *now* i_p_valid effect is felt

    yield dut.p.i_data.eq(2)
    yield
    yield dut.n.i_ready.eq(0) # begin going into "stall" (next stage says ready)
    yield dut.p.i_data.eq(9)
    yield
    yield dut.p.i_valid.eq(0)
    yield dut.p.i_data.eq(12)
    yield
    yield dut.p.i_data.eq(32)
    yield dut.n.i_ready.eq(1)
    yield
    yield from check_o_n_valid(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_valid(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_valid(dut, 0) # buffer outputted, *now* we're done.
    yield


def testbench2(dut):
    #yield dut.p.i_rst.eq(1)
    yield dut.n.i_ready.eq(0)
    #yield dut.p.o_ready.eq(0)
    yield
    yield
    #yield dut.p.i_rst.eq(0)
    yield dut.n.i_ready.eq(1)
    yield dut.p.i_data.eq(5)
    yield dut.p.i_valid.eq(1)
    yield

    yield dut.p.i_data.eq(7)
    yield from check_o_n_valid(dut, 0) # effects of i_p_valid delayed 2 clocks
    yield
    yield from check_o_n_valid(dut, 0) # effects of i_p_valid delayed 2 clocks

    yield dut.p.i_data.eq(2)
    yield
    yield from check_o_n_valid(dut, 1) # ok *now* i_p_valid effect is felt
    yield dut.n.i_ready.eq(0) # begin going into "stall" (next stage says ready)
    yield dut.p.i_data.eq(9)
    yield
    yield dut.p.i_valid.eq(0)
    yield dut.p.i_data.eq(12)
    yield
    yield dut.p.i_data.eq(32)
    yield dut.n.i_ready.eq(1)
    yield
    yield from check_o_n_valid(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_valid(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_valid(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_valid(dut, 0) # buffer outputted, *now* we're done.
    yield
    yield
    yield


class Test3:
    def __init__(self, dut, resultfn):
        self.dut = dut
        self.resultfn = resultfn
        self.data = []
        for i in range(num_tests):
            #data.append(randint(0, 1<<16-1))
            self.data.append(i+1)
        self.i = 0
        self.o = 0

    def send(self):
        while self.o != len(self.data):
            send_range = randint(0, 3)
            for j in range(randint(1,10)):
                if send_range == 0:
                    send = True
                else:
                    send = randint(0, send_range) != 0
                o_p_ready = yield self.dut.p.o_ready
                if not o_p_ready:
                    yield
                    continue
                if send and self.i != len(self.data):
                    yield self.dut.p.i_valid.eq(1)
                    yield self.dut.p.i_data.eq(self.data[self.i])
                    self.i += 1
                else:
                    yield self.dut.p.i_valid.eq(0)
                yield

    def rcv(self):
        while self.o != len(self.data):
            stall_range = randint(0, 3)
            for j in range(randint(1,10)):
                stall = randint(0, stall_range) != 0
                yield self.dut.n.i_ready.eq(stall)
                yield
                o_n_valid = yield self.dut.n.o_valid
                i_n_ready = yield self.dut.n.i_ready
                if not o_n_valid or not i_n_ready:
                    continue
                o_data = yield self.dut.n.o_data
                self.resultfn(o_data, self.data[self.o], self.i, self.o)
                self.o += 1
                if self.o == len(self.data):
                    break

def test3_resultfn(o_data, expected, i, o):
    assert o_data == expected + 1, \
                "%d-%d data %x not match %x\n" \
                % (i, o, o_data, expected)

class Test5:
    def __init__(self, dut, resultfn):
        self.dut = dut
        self.resultfn = resultfn
        self.data = []
        for i in range(num_tests):
            self.data.append((randint(0, 1<<16-1), randint(0, 1<<16-1)))
        self.i = 0
        self.o = 0

    def send(self):
        while self.o != len(self.data):
            send_range = randint(0, 3)
            for j in range(randint(1,10)):
                if send_range == 0:
                    send = True
                else:
                    send = randint(0, send_range) != 0
                o_p_ready = yield self.dut.p.o_ready
                if not o_p_ready:
                    yield
                    continue
                if send and self.i != len(self.data):
                    yield self.dut.p.i_valid.eq(1)
                    for v in self.dut.set_input(self.data[self.i]):
                        yield v
                    self.i += 1
                else:
                    yield self.dut.p.i_valid.eq(0)
                yield

    def rcv(self):
        while self.o != len(self.data):
            stall_range = randint(0, 3)
            for j in range(randint(1,10)):
                stall = randint(0, stall_range) != 0
                yield self.dut.n.i_ready.eq(stall)
                yield
                o_n_valid = yield self.dut.n.o_valid
                i_n_ready = yield self.dut.n.i_ready
                if not o_n_valid or not i_n_ready:
                    continue
                o_data = yield self.dut.n.o_data
                self.resultfn(o_data, self.data[self.o], self.i, self.o)
                self.o += 1
                if self.o == len(self.data):
                    break

def test5_resultfn(o_data, expected, i, o):
    res = expected[0] + expected[1]
    assert o_data == res, \
                "%d-%d data %x not match %s\n" \
                % (i, o, o_data, repr(expected))

def testbench4(dut):
    data = []
    for i in range(num_tests):
        #data.append(randint(0, 1<<16-1))
        data.append(i+1)
    i = 0
    o = 0
    while True:
        stall = randint(0, 3) != 0
        send = randint(0, 5) != 0
        yield dut.n.i_ready.eq(stall)
        o_p_ready = yield dut.p.o_ready
        if o_p_ready:
            if send and i != len(data):
                yield dut.p.i_valid.eq(1)
                yield dut.p.i_data.eq(data[i])
                i += 1
            else:
                yield dut.p.i_valid.eq(0)
        yield
        o_n_valid = yield dut.n.o_valid
        i_n_ready = yield dut.n.i_ready
        if o_n_valid and i_n_ready:
            o_data = yield dut.n.o_data
            assert o_data == data[o] + 2, "%d-%d data %x not match %x\n" \
                                        % (i, o, o_data, data[o])
            o += 1
            if o == len(data):
                break


class ExampleBufPipe2:
    """
        connect these:  ------|---------------|
                              v               v
        i_p_valid >>in  pipe1 o_n_valid out>> i_p_valid >>in  pipe2
        o_p_ready <<out pipe1 i_n_ready <<in  o_p_ready <<out pipe2
        p_i_data  >>in  pipe1 p_i_data  out>> n_o_data  >>in  pipe2
    """
    def __init__(self):
        self.pipe1 = ExampleBufPipe()
        self.pipe2 = ExampleBufPipe()

        # input
        self.p = PrevControl()
        self.p.i_data = Signal(32) # >>in - comes in from the PREVIOUS stage

        # output
        self.n = NextControl()
        self.n.o_data = Signal(32) # out>> - goes out to the NEXT stage

    def elaborate(self, platform):
        m = Module()
        m.submodules.pipe1 = self.pipe1
        m.submodules.pipe2 = self.pipe2

        # connect inter-pipe input/output valid/ready/data
        m.d.comb += self.pipe1.connect_to_next(self.pipe2)

        # inputs/outputs to the module: pipe1 connections here (LHS)
        m.d.comb += self.pipe1.connect_in(self)

        # now pipe2 connections (RHS)
        m.d.comb += self.pipe2.connect_out(self)

        return m

class SetLessThan:
    def __init__(self, width, signed):
        self.src1 = Signal((width, signed))
        self.src2 = Signal((width, signed))
        self.output = Signal(width)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.output.eq(Mux(self.src1 < self.src2, 1, 0))
        return m


class LTStage:
    def __init__(self):
        self.slt = SetLessThan(16, True)

    def ispec(self):
        return (Signal(16), Signal(16))

    def ospec(self):
        return Signal(16)

    def setup(self, m, i):
        self.o = Signal(16)
        m.submodules.slt = self.slt
        m.d.comb += self.slt.src1.eq(i[0])
        m.d.comb += self.slt.src2.eq(i[1])
        m.d.comb += self.o.eq(self.slt.output)

    def process(self, i):
        return self.o


class ExampleLTCombPipe(CombPipe):
    """ an example of how to use the combinatorial pipeline.
    """

    def __init__(self):
        stage = LTStage()
        CombPipe.__init__(self, stage)


def test6_resultfn(o_data, expected, i, o):
    res = 1 if expected[0] < expected[1] else 0
    assert o_data == res, \
                "%d-%d data %x not match %s\n" \
                % (i, o, o_data, repr(expected))


num_tests = 1000

if __name__ == '__main__':
    print ("test 1")
    dut = ExampleBufPipe()
    run_simulation(dut, testbench(dut), vcd_name="test_bufpipe.vcd")

    print ("test 2")
    dut = ExampleBufPipe2()
    run_simulation(dut, testbench2(dut), vcd_name="test_bufpipe2.vcd")

    print ("test 3")
    dut = ExampleBufPipe()
    test = Test3(dut, test3_resultfn)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_bufpipe3.vcd")

    print ("test 3.5")
    dut = ExampleCombPipe()
    test = Test3(dut, test3_resultfn)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_combpipe3.vcd")

    print ("test 4")
    dut = ExampleBufPipe2()
    run_simulation(dut, testbench4(dut), vcd_name="test_bufpipe4.vcd")

    print ("test 5")
    dut = ExampleBufPipeAdd()
    test = Test5(dut, test5_resultfn)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_bufpipe5.vcd")

    print ("test 6")
    dut = ExampleLTCombPipe()
    test = Test5(dut, test6_resultfn)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_ltcomb6.vcd")


""" Unit tests for Buffered and Unbuffered pipelines

    contains useful worked examples of how to use the Pipeline API,
    including:

    * Combinatorial Stage "Chaining"
    * class-based data stages
    * nmigen module-based data stages
    * special nmigen module-based data stage, where the stage *is* the module
    * Record-based data stages
    * static-class data stages
    * multi-stage pipelines (and how to connect them)
    * how to *use* the pipelines (see Test5) - how to get data in and out

"""

from nmigen import Module, Signal, Mux, Const
from nmigen.hdl.rec import Record
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

from example_buf_pipe import ExampleBufPipe, ExampleBufPipeAdd
from example_buf_pipe import ExamplePipeline, UnbufferedPipeline
from example_buf_pipe import ExampleStageCls
from example_buf_pipe import PrevControl, NextControl, BufferedPipeline
from example_buf_pipe import StageChain, ControlBase, StageCls
from singlepipe import UnbufferedPipeline2

from random import randint


def check_o_n_valid(dut, val):
    o_n_valid = yield dut.n.o_valid
    assert o_n_valid == val

def check_o_n_valid2(dut, val):
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
    yield from check_o_n_valid2(dut, 0) # effects of i_p_valid delayed 2 clocks
    yield
    yield from check_o_n_valid2(dut, 0) # effects of i_p_valid delayed 2 clocks

    yield dut.p.i_data.eq(2)
    yield
    yield from check_o_n_valid2(dut, 1) # ok *now* i_p_valid effect is felt
    yield dut.n.i_ready.eq(0) # begin going into "stall" (next stage says ready)
    yield dut.p.i_data.eq(9)
    yield
    yield dut.p.i_valid.eq(0)
    yield dut.p.i_data.eq(12)
    yield
    yield dut.p.i_data.eq(32)
    yield dut.n.i_ready.eq(1)
    yield
    yield from check_o_n_valid2(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_valid2(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_valid2(dut, 1) # buffer still needs to output
    yield
    yield from check_o_n_valid2(dut, 0) # buffer outputted, *now* we're done.
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
                i_n_ready = yield self.dut.n.i_ready_test
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

def data_placeholder():
        data = []
        for i in range(num_tests):
            d = PlaceHolder()
            d.src1 = randint(0, 1<<16-1)
            d.src2 = randint(0, 1<<16-1)
            data.append(d)
        return data

def data_dict():
        data = []
        for i in range(num_tests):
            data.append({'src1': randint(0, 1<<16-1),
                         'src2': randint(0, 1<<16-1)})
        return data


class Test5:
    def __init__(self, dut, resultfn, data=None, stage_ctl=False):
        self.dut = dut
        self.resultfn = resultfn
        self.stage_ctl = stage_ctl
        if data:
            self.data = data
        else:
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
                ready = randint(0, stall_range) != 0
                yield self.dut.n.i_ready.eq(ready)
                yield
                o_n_valid = yield self.dut.n.o_valid
                i_n_ready = yield self.dut.n.i_ready_test
                if not o_n_valid or not i_n_ready:
                    continue
                if isinstance(self.dut.n.o_data, Record):
                    o_data = {}
                    dod = self.dut.n.o_data
                    for k, v in dod.fields.items():
                        o_data[k] = yield v
                else:
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
        i_n_ready = yield dut.n.i_ready_test
        if o_n_valid and i_n_ready:
            o_data = yield dut.n.o_data
            assert o_data == data[o] + 2, "%d-%d data %x not match %x\n" \
                                        % (i, o, o_data, data[o])
            o += 1
            if o == len(data):
                break

######################################################################
# Test 2 and 4
######################################################################

class ExampleBufPipe2(ControlBase):
    """ Example of how to do chained pipeline stages.
    """

    def elaborate(self, platform):
        m = Module()

        pipe1 = ExampleBufPipe()
        pipe2 = ExampleBufPipe()

        m.submodules.pipe1 = pipe1
        m.submodules.pipe2 = pipe2

        m.d.comb += self.connect([pipe1, pipe2])

        return m


######################################################################
# Test 9
######################################################################

class ExampleBufPipeChain2(BufferedPipeline):
    """ connects two stages together as a *single* combinatorial stage.
    """
    def __init__(self):
        stage1 = ExampleStageCls()
        stage2 = ExampleStageCls()
        combined = StageChain([stage1, stage2])
        BufferedPipeline.__init__(self, combined)


def data_chain2():
        data = []
        for i in range(num_tests):
            data.append(randint(0, 1<<16-2))
        return data


def test9_resultfn(o_data, expected, i, o):
    res = expected + 2
    assert o_data == res, \
                "%d-%d data %x not match %s\n" \
                % (i, o, o_data, repr(expected))


######################################################################
# Test 6 and 10
######################################################################

class SetLessThan:
    def __init__(self, width, signed):
        self.m = Module()
        self.src1 = Signal((width, signed), name="src1")
        self.src2 = Signal((width, signed), name="src2")
        self.output = Signal(width, name="out")

    def elaborate(self, platform):
        self.m.d.comb += self.output.eq(Mux(self.src1 < self.src2, 1, 0))
        return self.m


class LTStage(StageCls):
    """ module-based stage example
    """
    def __init__(self):
        self.slt = SetLessThan(16, True)

    def ispec(self):
        return (Signal(16, name="sig1"), Signal(16, "sig2"))

    def ospec(self):
        return Signal(16, "out")

    def setup(self, m, i):
        self.o = Signal(16)
        m.submodules.slt = self.slt
        m.d.comb += self.slt.src1.eq(i[0])
        m.d.comb += self.slt.src2.eq(i[1])
        m.d.comb += self.o.eq(self.slt.output)

    def process(self, i):
        return self.o


class LTStageDerived(SetLessThan, StageCls):
    """ special version of a nmigen module where the module is also a stage

        shows that you don't actually need to combinatorially connect
        to the outputs, or add the module as a submodule: just return
        the module output parameter(s) from the Stage.process() function
    """

    def __init__(self):
        SetLessThan.__init__(self, 16, True)

    def ispec(self):
        return (Signal(16), Signal(16))

    def ospec(self):
        return Signal(16)

    def setup(self, m, i):
        m.submodules.slt = self
        m.d.comb += self.src1.eq(i[0])
        m.d.comb += self.src2.eq(i[1])

    def process(self, i):
        return self.output


class ExampleLTPipeline(UnbufferedPipeline):
    """ an example of how to use the unbuffered pipeline.
    """

    def __init__(self):
        stage = LTStage()
        UnbufferedPipeline.__init__(self, stage)


class ExampleLTBufferedPipeDerived(BufferedPipeline):
    """ an example of how to use the buffered pipeline.
    """

    def __init__(self):
        stage = LTStageDerived()
        BufferedPipeline.__init__(self, stage)


def test6_resultfn(o_data, expected, i, o):
    res = 1 if expected[0] < expected[1] else 0
    assert o_data == res, \
                "%d-%d data %x not match %s\n" \
                % (i, o, o_data, repr(expected))


######################################################################
# Test 7
######################################################################

class ExampleAddRecordStage(StageCls):
    """ example use of a Record
    """

    record_spec = [('src1', 16), ('src2', 16)]
    def ispec(self):
        """ returns a Record using the specification
        """
        return Record(self.record_spec)

    def ospec(self):
        return Record(self.record_spec)

    def process(self, i):
        """ process the input data, returning a dictionary with key names
            that exactly match the Record's attributes.
        """
        return {'src1': i.src1 + 1,
                'src2': i.src2 + 1}

######################################################################
# Test 11
######################################################################

class ExampleAddRecordPlaceHolderStage(StageCls):
    """ example use of a Record, with a placeholder as the processing result
    """

    record_spec = [('src1', 16), ('src2', 16)]
    def ispec(self):
        """ returns a Record using the specification
        """
        return Record(self.record_spec)

    def ospec(self):
        return Record(self.record_spec)

    def process(self, i):
        """ process the input data, returning a PlaceHolder class instance
            with attributes that exactly match those of the Record.
        """
        o = PlaceHolder()
        o.src1 = i.src1 + 1
        o.src2 = i.src2 + 1
        return o


class PlaceHolder: pass


class ExampleAddRecordPipe(UnbufferedPipeline):
    """ an example of how to use the combinatorial pipeline.
    """

    def __init__(self):
        stage = ExampleAddRecordStage()
        UnbufferedPipeline.__init__(self, stage)


def test7_resultfn(o_data, expected, i, o):
    res = (expected['src1'] + 1, expected['src2'] + 1)
    assert o_data['src1'] == res[0] and o_data['src2'] == res[1], \
                "%d-%d data %s not match %s\n" \
                % (i, o, repr(o_data), repr(expected))


class ExampleAddRecordPlaceHolderPipe(UnbufferedPipeline):
    """ an example of how to use the combinatorial pipeline.
    """

    def __init__(self):
        stage = ExampleAddRecordPlaceHolderStage()
        UnbufferedPipeline.__init__(self, stage)


def test11_resultfn(o_data, expected, i, o):
    res1 = expected.src1 + 1
    res2 = expected.src2 + 1
    assert o_data['src1'] == res1 and o_data['src2'] == res2, \
                "%d-%d data %s not match %s\n" \
                % (i, o, repr(o_data), repr(expected))


######################################################################
# Test 8
######################################################################


class Example2OpClass:
    """ an example of a class used to store 2 operands.
        requires an eq function, to conform with the pipeline stage API
    """

    def __init__(self):
        self.op1 = Signal(16)
        self.op2 = Signal(16)

    def eq(self, i):
        return [self.op1.eq(i.op1), self.op2.eq(i.op2)]


class ExampleAddClassStage(StageCls):
    """ an example of how to use the buffered pipeline, as a class instance
    """

    def ispec(self):
        """ returns an instance of an Example2OpClass.
        """
        return Example2OpClass()

    def ospec(self):
        """ returns an output signal which will happen to contain the sum
            of the two inputs
        """
        return Signal(16)

    def process(self, i):
        """ process the input data (sums the values in the tuple) and returns it
        """
        return i.op1 + i.op2


class ExampleBufPipeAddClass(BufferedPipeline):
    """ an example of how to use the buffered pipeline, using a class instance
    """

    def __init__(self):
        addstage = ExampleAddClassStage()
        BufferedPipeline.__init__(self, addstage)


class TestInputAdd:
    """ the eq function, called by set_input, needs an incoming object
        that conforms to the Example2OpClass.eq function requirements
        easiest way to do that is to create a class that has the exact
        same member layout (self.op1, self.op2) as Example2OpClass
    """
    def __init__(self, op1, op2):
        self.op1 = op1
        self.op2 = op2


def test8_resultfn(o_data, expected, i, o):
    res = expected.op1 + expected.op2 # these are a TestInputAdd instance
    assert o_data == res, \
                "%d-%d data %x not match %s\n" \
                % (i, o, o_data, repr(expected))

def data_2op():
        data = []
        for i in range(num_tests):
            data.append(TestInputAdd(randint(0, 1<<16-1), randint(0, 1<<16-1)))
        return data


######################################################################
# Test 12
######################################################################

class ExampleStageDelayCls(StageCls):
    """ an example of how to use the buffered pipeline, in a static class
        fashion
    """

    def __init__(self):
        self.count = Signal(2)

    def ispec(self):
        return Signal(16, name="example_input_signal")

    def ospec(self):
        return Signal(16, name="example_output_signal")

    @property
    def d_ready(self):
        return self.count == 2
        return Const(1)

    @property
    def d_valid(self):
        return self.count == 0
        return Const(1)

    def process(self, i):
        """ process the input data and returns it (adds 1)
        """
        return i + 1

    def elaborate(self, platform):
        m = Module()
        m.d.sync += self.count.eq(self.count + 1)
        return m


class ExampleBufDelayedPipe(BufferedPipeline):

    def __init__(self):
        stage = ExampleStageDelayCls()
        BufferedPipeline.__init__(self, stage, stage_ctl=True)

    def elaborate(self, platform):
        m = BufferedPipeline.elaborate(self, platform)
        m.submodules.stage = self.stage
        return m


class ExampleBufPipe3(ControlBase):
    """ Example of how to do delayed pipeline, where the stage signals
        whether it is ready.
    """

    def elaborate(self, platform):
        m = ControlBase._elaborate(self, platform)

        #pipe1 = ExampleBufPipe()
        pipe1 = ExampleBufDelayedPipe()
        pipe2 = ExampleBufDelayedPipe()

        m.submodules.pipe1 = pipe1
        m.submodules.pipe2 = pipe2

        m.d.comb += self.connect([pipe1, pipe2])

        return m

def data_chain1():
        data = []
        for i in range(num_tests):
            data.append(randint(0, 1<<16-2))
        return data


def test12_resultfn(o_data, expected, i, o):
    res = expected + 1
    assert o_data == res, \
                "%d-%d data %x not match %x\n" \
                % (i, o, o_data, res)


######################################################################
# Test 13
######################################################################

class ExampleUnBufDelayedPipe(UnbufferedPipeline):

    def __init__(self):
        stage = ExampleStageDelayCls()
        UnbufferedPipeline.__init__(self, stage, stage_ctl=True)

    def elaborate(self, platform):
        m = UnbufferedPipeline.elaborate(self, platform)
        m.submodules.stage = self.stage
        return m

######################################################################
# Test 999 - XXX FAILS
######################################################################

class ExampleBufAdd1Pipe(BufferedPipeline):

    def __init__(self):
        stage = ExampleStageCls()
        BufferedPipeline.__init__(self, stage)


class ExampleUnBufAdd1Pipe(UnbufferedPipeline2):

    def __init__(self):
        stage = ExampleStageCls()
        UnbufferedPipeline2.__init__(self, stage)


class ExampleBufUnBufPipe(ControlBase):

    def elaborate(self, platform):
        m = ControlBase._elaborate(self, platform)

        # XXX currently fails: any other permutation works fine.
        # p1=u,p2=b ok p1=u,p2=u ok p1=b,p2=b ok
        # also fails using UnbufferedPipeline as well
        #pipe1 = ExampleUnBufAdd1Pipe()
        #pipe2 = ExampleBufAdd1Pipe()
        pipe1 = ExampleBufAdd1Pipe()
        pipe2 = ExampleUnBufAdd1Pipe()

        m.submodules.pipe1 = pipe1
        m.submodules.pipe2 = pipe2

        m.d.comb += self.connect([pipe1, pipe2])

        return m


######################################################################
# Unit Tests
######################################################################

num_tests = 100

if __name__ == '__main__':
    print ("test 1")
    dut = ExampleBufPipe()
    run_simulation(dut, testbench(dut), vcd_name="test_bufpipe.vcd")

    print ("test 2")
    dut = ExampleBufPipe2()
    run_simulation(dut, testbench2(dut), vcd_name="test_bufpipe2.vcd")
    ports = [dut.p.i_valid, dut.n.i_ready,
             dut.n.o_valid, dut.p.o_ready] + \
             [dut.p.i_data] + [dut.n.o_data]
    vl = rtlil.convert(dut, ports=ports)
    with open("test_bufpipe2.il", "w") as f:
        f.write(vl)


    print ("test 3")
    dut = ExampleBufPipe()
    test = Test3(dut, test3_resultfn)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_bufpipe3.vcd")

    print ("test 3.5")
    dut = ExamplePipeline()
    test = Test3(dut, test3_resultfn)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_combpipe3.vcd")

    print ("test 4")
    dut = ExampleBufPipe2()
    run_simulation(dut, testbench4(dut), vcd_name="test_bufpipe4.vcd")

    print ("test 5")
    dut = ExampleBufPipeAdd()
    test = Test5(dut, test5_resultfn, stage_ctl=True)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_bufpipe5.vcd")

    print ("test 6")
    dut = ExampleLTPipeline()
    test = Test5(dut, test6_resultfn)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_ltcomb6.vcd")

    ports = [dut.p.i_valid, dut.n.i_ready,
             dut.n.o_valid, dut.p.o_ready] + \
             list(dut.p.i_data) + [dut.n.o_data]
    vl = rtlil.convert(dut, ports=ports)
    with open("test_ltcomb_pipe.il", "w") as f:
        f.write(vl)

    print ("test 7")
    dut = ExampleAddRecordPipe()
    data=data_dict()
    test = Test5(dut, test7_resultfn, data=data)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_addrecord.vcd")

    ports = [dut.p.i_valid, dut.n.i_ready,
             dut.n.o_valid, dut.p.o_ready,
             dut.p.i_data.src1, dut.p.i_data.src2,
             dut.n.o_data.src1, dut.n.o_data.src2]
    vl = rtlil.convert(dut, ports=ports)
    with open("test_recordcomb_pipe.il", "w") as f:
        f.write(vl)

    print ("test 8")
    dut = ExampleBufPipeAddClass()
    data=data_2op()
    test = Test5(dut, test8_resultfn, data=data)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_bufpipe8.vcd")

    print ("test 9")
    dut = ExampleBufPipeChain2()
    ports = [dut.p.i_valid, dut.n.i_ready,
             dut.n.o_valid, dut.p.o_ready] + \
             [dut.p.i_data] + [dut.n.o_data]
    vl = rtlil.convert(dut, ports=ports)
    with open("test_bufpipechain2.il", "w") as f:
        f.write(vl)

    data = data_chain2()
    test = Test5(dut, test9_resultfn, data=data)
    run_simulation(dut, [test.send, test.rcv],
                        vcd_name="test_bufpipechain2.vcd")

    print ("test 10")
    dut = ExampleLTBufferedPipeDerived()
    test = Test5(dut, test6_resultfn)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_ltbufpipe10.vcd")
    vl = rtlil.convert(dut, ports=ports)
    with open("test_ltbufpipe10.il", "w") as f:
        f.write(vl)

    print ("test 11")
    dut = ExampleAddRecordPlaceHolderPipe()
    data=data_placeholder()
    test = Test5(dut, test11_resultfn, data=data)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_addrecord.vcd")


    print ("test 12")
    #dut = ExampleBufPipe3()
    dut = ExampleBufDelayedPipe()
    data = data_chain1()
    test = Test5(dut, test12_resultfn, data=data)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_bufpipe12.vcd")
    ports = [dut.p.i_valid, dut.n.i_ready,
             dut.n.o_valid, dut.p.o_ready] + \
             [dut.p.i_data] + [dut.n.o_data]
    vl = rtlil.convert(dut, ports=ports)
    with open("test_bufpipe12.il", "w") as f:
        f.write(vl)

    print ("test 13")
    #dut = ExampleBufPipe3()
    dut = ExampleUnBufDelayedPipe()
    data = data_chain1()
    test = Test5(dut, test12_resultfn, data=data)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_unbufpipe13.vcd")
    ports = [dut.p.i_valid, dut.n.i_ready,
             dut.n.o_valid, dut.p.o_ready] + \
             [dut.p.i_data] + [dut.n.o_data]
    vl = rtlil.convert(dut, ports=ports)
    with open("test_unbufpipe13.il", "w") as f:
        f.write(vl)

    print ("test 999 (expected to fail, which is a bug)")
    dut = ExampleBufUnBufPipe()
    data = data_chain1()
    test = Test5(dut, test9_resultfn, data=data)
    run_simulation(dut, [test.send, test.rcv], vcd_name="test_bufunbuf999.vcd")
    ports = [dut.p.i_valid, dut.n.i_ready,
             dut.n.o_valid, dut.p.o_ready] + \
             [dut.p.i_data] + [dut.n.o_data]
    vl = rtlil.convert(dut, ports=ports)
    with open("test_bufunbuf999.il", "w") as f:
        f.write(vl)


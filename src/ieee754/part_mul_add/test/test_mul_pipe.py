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

from nmigen import Module, Signal, Mux, Const, Elaboratable
from nmigen.hdl.rec import Record
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil

from nmutil.singlepipe import ControlBase
from nmutil.singlepipe import MaskCancellable

from random import randint, seed

#seed(4)


from ieee754.part_mul_add.test.test_multiply import SIMDMulLane, simd_mul
from ieee754.part_mul_add.mul_pipe import MulPipe_8_16_32_64, InputData
from ieee754.part_mul_add.multiply import OP_MUL_LOW, PartitionPoints


def resultfn_3(data_o, expected, i, o):
    assert data_o == expected + 1, \
                "%d-%d data %x not match %x\n" \
                % (i, o, data_o, expected)

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
                #send = True
                o_p_ready = yield self.dut.p.ready_o
                if not o_p_ready:
                    yield
                    continue
                if send and self.i != len(self.data):
                    yield self.dut.p.valid_i.eq(1)
                    pd = self.dut.p.data_i
                    di = self.data[self.i]
                    print ("send", j, hex(di.a), hex(di.b))
                    yield pd.a.eq(di.a)
                    yield pd.b.eq(di.b)
                    for k in pd.part_pts.keys():
                        yield pd.part_pts[k].eq(di.part_pts[k])
                    for j in range(len(pd.part_ops)):
                        yield pd.part_ops[j].eq(di.part_ops[j])
                    self.i += 1
                else:
                    yield self.dut.p.valid_i.eq(0)
                yield

    def rcv(self):
        while self.o != len(self.data):
            stall_range = randint(0, 3)
            for j in range(randint(1,10)):
                ready = randint(0, stall_range) != 0
                #ready = True
                yield self.dut.n.ready_i.eq(ready)
                yield
                o_n_valid = yield self.dut.n.valid_o
                i_n_ready = yield self.dut.n.ready_i_test
                if not o_n_valid or not i_n_ready:
                    continue
                data_o = yield self.dut.n.data_o.output
                print ("rcv", j, hex(data_o))
                self.resultfn(data_o, self.data[self.o], self.i, self.o)
                self.o += 1
                if self.o == len(self.data):
                    break


def resultfn_5(data_o, expected, i, o):
    res = expected[0] + expected[1]
    assert data_o == res, \
                "%d-%d data %x not match %s\n" \
                % (i, o, data_o, repr(expected))


class ExampleAddRecordPlaceHolderStage:
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


# a dummy class that may have stuff assigned to instances once created
class PlaceHolder: pass


######################################################################
# Test 8
######################################################################


class TestInputMul:
    """ the eq function, called by set_input, needs an incoming object
        that conforms to the Example2OpClass.eq function requirements
        easiest way to do that is to create a class that has the exact
        same member layout (self.op1, self.op2) as Example2OpClass
    """
    def __init__(self, a, b):

        self.a = a
        self.b = b

        self.part_pts = PartitionPoints()
        for i in range(8, 64, 8):
            self.part_pts[i] = False

        # set to 16-bit partitions
        for i in range(16, 64, 16):
            self.part_pts[i] = True

        self.part_ops = [Signal() for i in range(8)]

def simd_calc_result(a, b):
    lanes = [SIMDMulLane(False,
                         False,
                         16,
                         False)]*4
    so, si = simd_mul(a, b, lanes)
    return so

def resultfn_8(data_o, expected, i, o):
    res = simd_calc_result(expected.a, expected.b)
    assert data_o == res, \
                "%d-%d data %x res %x not match %s\n" \
                % (i, o, data_o, res, repr(expected))

def data_2op():
    data = []
    for i in range(num_tests):
        a = randint(0, 1<<64-1)
        b = randint(0, 1<<64-1)
        data.append(TestInputMul(a, b))
    return data




######################################################################
# Unit Tests
######################################################################

num_tests = 10

def test0():
    maskwid = num_tests
    print ("test 0")
    dut = MaskCancellablePipe(maskwid)
    data = data_chain0(maskwid)
    test = TestMask(dut, resultfn_0, maskwid, data=data)
    run_simulation(dut, [test.send, test.rcv],
                        vcd_name="test_maskchain0.vcd")


def test8():
    print ("test 8")
    dut = MulPipe_8_16_32_64()
    ports = [dut.p.valid_i, dut.n.ready_i,
             dut.n.valid_o, dut.p.ready_o,
             dut.a, dut.b, dut.output]
    #vl = rtlil.convert(dut, ports=ports)
    #with open("test_mul_pipe_8_16_32_64.il", "w") as f:
    #    f.write(vl)
    data=data_2op()
    test = Test5(dut, resultfn_8, data=data)
    run_simulation(dut, [test.send, test.rcv],
                   vcd_name="test_mul_pipe_8_16_32_64.vcd")


def test_simd_mul():
    lanes = [SIMDMulLane(True,
                         True,
                         8,
                         True),
             SIMDMulLane(False,
                         False,
                         8,
                         True),
                 SIMDMulLane(True,
                             True,
                             16,
                             False),
                 SIMDMulLane(True,
                             False,
                             32,
                             True)]
    a = 0x0123456789ABCDEF
    b = 0xFEDCBA9876543210
    output = 0x0121FA00FE1C28FE
    intermediate_output = 0x0121FA0023E20B28C94DFE1C280AFEF0
    so, si = simd_mul(a, b, lanes)
    print (hex(so), hex(si))
    print (hex(output), hex(intermediate_output))

def test_simd_mul1():
    lanes = [SIMDMulLane(True,
                         True,
                         8,
                         False),
             SIMDMulLane(False,
                         False,
                         8,
                         True),
             ]
    a = 0x1217
    b = 0x5925
    #output = 0x0121FA00FE1C28FE
    #intermediate_output = 0x0121FA0023E20B28C94DFE1C280AFEF0
    so, si = simd_mul(a, b, lanes)
    print (hex(so), hex(si))
    #print (hex(output), hex(intermediate_output))


if __name__ == '__main__':
    test8()
    #test0_1()
    #test_simd_mul()
    #test_simd_mul1()

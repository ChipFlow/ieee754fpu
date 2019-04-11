from nmigen import Module, Signal, Mux, Const
from nmigen.hdl.rec import Record, Layout, DIR_NONE
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil
from nmigen.compat.fhdl.bitcontainer import value_bits_sign
from singlepipe import flatten


class RecordObject(Record):
    def __init__(self, name=None):
        Record.__init__(self, layout=[], name=None)

    def __setattr__(self, k, v):
        if k in dir(Record) or "fields" not in self.__dict__:
            return object.__setattr__(self, k, v)
        self.__dict__["fields"][k] = v
        if isinstance(v, Record):
            newlayout = {k: (k, v.layout)}
        else:
            newlayout = {k: (k, v.shape())}
        self.__dict__["layout"].fields.update(newlayout)


class RecordTest:

    def __init__(self):
        self.r1 = RecordObject()
        self.r1.sig1 = Signal(32)
        self.r1.r2 = RecordObject()
        self.r1.r2.sig2 = Signal(32)
        self.r1.r3 = RecordObject()
        self.r1.r3.sig3 = Signal(32)
        self.sig123 = Signal(96)

    def elaborate(self, platform):
        m = Module()

        sig1 = Signal(32)
        m.d.comb += sig1.eq(self.r1.sig1)
        sig2 = Signal(32)
        m.d.comb += sig2.eq(self.r1.r2.sig2)

        print (self.r1.fields)
        print (self.r1.shape())
        print (len(self.r1))
        m.d.comb += self.sig123.eq(flatten(self.r1))

        return m


def testbench(dut):
    yield dut.r1.sig1.eq(5)
    yield dut.r1.r2.sig2.eq(10)
    
    sig1 = yield dut.r1.sig1
    assert sig1 == 5
    sig2 = yield dut.r1.r2.sig2
    assert sig2 == 10



######################################################################
# Unit Tests
######################################################################

if __name__ == '__main__':
    print ("test 1")
    dut = RecordTest()
    run_simulation(dut, testbench(dut), vcd_name="test_record1.vcd")
    vl = rtlil.convert(dut, ports=[dut.sig123, dut.r1.sig1, dut.r1.r2.sig2])
    with open("test_record1.il", "w") as f:
        f.write(vl)


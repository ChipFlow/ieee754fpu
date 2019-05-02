from nmigen import Module, Signal, Mux, Const, Elaboratable
from nmigen.hdl.rec import Record, Layout, DIR_NONE
from nmigen.compat.sim import run_simulation
from nmigen.cli import verilog, rtlil
from nmigen.compat.fhdl.bitcontainer import value_bits_sign
from nmutil.singlepipe import cat, RecordObject


class RecordTest:

    def __init__(self):
        self.r1 = RecordObject()
        self.r1.sig1 = Signal(16)
        self.r1.r2 = RecordObject()
        self.r1.r2.sig2 = Signal(16)
        self.r1.r3 = RecordObject()
        self.r1.r3.sig3 = Signal(16)
        self.sig123 = Signal(48)

    def elaborate(self, platform):
        m = Module()

        sig1 = Signal(16)
        m.d.comb += sig1.eq(self.r1.sig1)
        sig2 = Signal(16)
        m.d.comb += sig2.eq(self.r1.r2.sig2)

        print (self.r1.fields)
        print (self.r1.shape())
        print ("width", len(self.r1))
        m.d.comb += self.sig123.eq(cat(self.r1))

        return m


def testbench(dut):
    yield dut.r1.sig1.eq(5)
    yield dut.r1.r2.sig2.eq(10)
    yield dut.r1.r3.sig3.eq(1)
    
    sig1 = yield dut.r1.sig1
    assert sig1 == 5
    sig2 = yield dut.r1.r2.sig2
    assert sig2 == 10

    yield

    sig123 = yield dut.sig123
    print ("sig123", hex(sig123))
    assert sig123 == 0x1000a0005



class RecordTest2(Elaboratable):

    def __init__(self):
        self.r1 = RecordObject()
        self.r1.sig1 = Signal(16)
        self.r1.r2 = RecordObject()
        self.r1.r2.sig2 = Signal(16)
        self.r1.r3 = RecordObject()
        self.r1.r3.sig3 = Signal(16)
        self.sig123 = Signal(48)

    def elaborate(self, platform):
        m = Module()

        m.d.comb += cat(self.r1).eq(self.sig123)

        return m


def testbench2(dut):
    
    sig123 = yield dut.sig123.eq(0x1000a0005)

    yield

    sig1 = yield dut.r1.sig1
    assert sig1 == 5
    sig2 = yield dut.r1.r2.sig2
    assert sig2 == 10
    sig3 = yield dut.r1.r3.sig3
    assert sig3 == 1



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

    print ("test 2")
    dut = RecordTest2()
    run_simulation(dut, testbench2(dut), vcd_name="test_record2.vcd")
    vl = rtlil.convert(dut, ports=[dut.sig123, dut.r1.sig1, dut.r1.r2.sig2])
    with open("test_record2.il", "w") as f:
        f.write(vl)


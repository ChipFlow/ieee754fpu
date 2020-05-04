from nmigen import Module, Signal, Elaboratable, Mux, Const
from nmigen.asserts import Assert, AnyConst, Assume
from nmigen.test.utils import FHDLTestCase
from nmigen.cli import rtlil

from ieee754.cordic.clz import CLZ
import unittest


# This defines a module to drive the device under test and assert
# properties about its outputs
class Driver(Elaboratable):
    def __init__(self):
        # inputs and outputs
        pass

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = 32

        m.submodules.dut = dut = CLZ(width)
        sig_in = Signal.like(dut.sig_in)
        count = Signal.like(dut.lz)


        m.d.comb += [
            sig_in.eq(AnyConst(width)),
            dut.sig_in.eq(sig_in),
            count.eq(dut.lz)]

        result = Const(width)
        for i in range(width):
            print(result)
            result_next = Signal.like(count, name="count_%d" % i)
            with m.If(sig_in[i] == 1):
                comb += result_next.eq(width-i-1)
            with m.Else():
                comb += result_next.eq(result)
            result = result_next

        result_sig = Signal.like(count)
        comb += result_sig.eq(result)

        comb += Assert(result_sig == count)
        
        # setup the inputs and outputs of the DUT as anyconst

        return m

class CLZTestCase(FHDLTestCase):
    def test_proof(self):
        module = Driver()
        self.assertFormal(module, mode="bmc", depth=4)
    def test_ilang(self):
        dut = Driver()
        vl = rtlil.convert(dut, ports=[])
        with open("clz.il", "w") as f:
            f.write(vl)

if __name__ == '__main__':
    unittest.main()

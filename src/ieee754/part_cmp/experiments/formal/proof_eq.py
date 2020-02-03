# Proof of correctness for partitioned equal signal combiner
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable, Mux
from nmigen.asserts import Assert, AnyConst
from nmigen.test.utils import FHDLTestCase
from nmigen.cli import rtlil

from ieee754.part_cmp.experiments.eq_combiner import EQCombiner
import unittest


# This defines a module to drive the device under test and assert
# properties about its outputs
class CombinerDriver(Elaboratable):
    def __init__(self):
        # inputs and outputs
        pass

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = 3

        # setup the inputs and outputs of the DUT as anyconst
        eqs = Signal(width)
        neqs = Signal(width)
        gates = Signal(width-1)
        out = Signal(width)
        comb += [eqs.eq(AnyConst(width)),
                     gates.eq(AnyConst(width)),
                     neqs.eq(~eqs)]

        m.submodules.dut = dut = EQCombiner(width)

        with m.Switch(gates):
            with m.Case(0b11):
                for i in range(width):
                    comb += Assert(out[i] == eqs[i])
            with m.Case(0b00):
                comb += Assert(out[0] == (eqs[0] & eqs[1] & eqs[2]))
                comb += Assert(out[1] == 0)
                comb += Assert(out[2] == 0)
            with m.Case(0b10):
                comb += Assert(out[0] == (eqs[0] & eqs[1]))
                comb += Assert(out[1] == 0)
                comb += Assert(out[2] == eqs[2])
            with m.Case(0b01):
                comb += Assert(out[0] == eqs[0])
                comb += Assert(out[1] == (eqs[1] & eqs[2]))
                comb += Assert(out[2] == 0)





        # connect up the inputs and outputs.
        comb += dut.neqs.eq(neqs)
        comb += dut.gates.eq(gates)
        comb += out.eq(dut.outputs)

        return m

class EQCombinerTestCase(FHDLTestCase):
    def test_combiner(self):
        module = CombinerDriver()
        self.assertFormal(module, mode="bmc", depth=4)
    def test_ilang(self):
        dut = EQCombiner(3)
        vl = rtlil.convert(dut, ports=dut.ports())
        with open("partition_combiner.il", "w") as f:
            f.write(vl)


if __name__ == '__main__':
    unittest.main()

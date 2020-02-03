# Proof of correctness for partitioned equal signal combiner
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable, Mux
from nmigen.asserts import Assert, AnyConst, Assume
from nmigen.test.utils import FHDLTestCase
from nmigen.cli import rtlil

from ieee754.part_cmp.experiments.gt_combiner import GTCombiner
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
        gts = Signal(width)
        gates = Signal(width-1)
        out = Signal(width)
        mux_input = Signal()
        comb += [eqs.eq(AnyConst(width)),
                 gates.eq(AnyConst(width)),
                 gts.eq(AnyConst(width)),
                 mux_input.eq(AnyConst(1))]


        m.submodules.dut = dut = GTCombiner(width)


        # If the mux_input is 0, then this should work exactly as
        # described in
        # https://libre-riscv.org/3d_gpu/architecture/dynamic_simd/gt/
        # except for 2 gate bits, not 3
        with m.If(mux_input == 0):
            with m.Switch(gates):
                with m.Case(0b11):
                    for i in range(out.width):
                        comb += Assert(out[i] == gts[i])
                with m.Case(0b10):
                    comb += Assert(out[2] == gts[2])
                    comb += Assert(out[1] == 0)
                    comb += Assert(out[0] == (gts[0] | (eqs[0] & gts[1])))
                with m.Case(0b01):
                    comb += Assert(out[2] == 0)
                    comb += Assert(out[1] == (gts[1] | (eqs[1] & gts[2])))
                    comb += Assert(out[0] == gts[0])
                with m.Case(0b00):
                    comb += Assert(out[2] == 0)
                    comb += Assert(out[1] == 0)
                    comb += Assert(out[0] == (gts[0] | (eqs[0] & (gts[1] | (eqs[1] & gts[2])))))
        # With the mux_input set to 1, this should work similarly to
        # eq_combiner. It appears this is the case, however the
        # ungated inputs are not set to 0 like they are in eq
        with m.Else():
            for i in range(gts.width):
                comb += Assume(gts[i] == 0)

            with m.Switch(gates):
                with m.Case(0b11):
                    for i in range(out.width):
                        comb += Assert(out[i] == eqs[i])
                with m.Case(0b00):
                    comb += Assert(out[0] == (eqs[0] & eqs[1] & eqs[2]))
                with m.Case(0b10):
                    comb += Assert(out[0] == (eqs[0] & eqs[1]))
                    comb += Assert(out[2] == eqs[2])
                with m.Case(0b01):
                    comb += Assert(out[0] == eqs[0])
                    comb += Assert(out[1] == (eqs[1] & eqs[2]))



        # connect up the inputs and outputs.
        comb += dut.eqs.eq(eqs)
        comb += dut.gts.eq(gts)
        comb += dut.gates.eq(gates)
        comb += dut.mux_input.eq(mux_input)
        comb += out.eq(dut.outputs)

        return m

class GTCombinerTestCase(FHDLTestCase):
    def test_gt_combiner(self):
        module = CombinerDriver()
        self.assertFormal(module, mode="bmc", depth=4)
    def test_ilang(self):
        dut = GTCombiner(3)
        vl = rtlil.convert(dut, ports=dut.ports())
        with open("partition_combiner.il", "w") as f:
            f.write(vl)


if __name__ == '__main__':
    unittest.main()

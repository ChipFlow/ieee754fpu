# Proof of correctness for FPCMP module
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable, Mux
from nmigen.asserts import Assert, AnyConst
from nmigen.test.utils import FHDLTestCase

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from ieee754.fpcmp.fpcmp import FPCMPPipeMod
from ieee754.pipeline import PipelineSpec
import unittest


# This defines a module to drive the device under test and assert
# properties about its outputs
class FPCMPDriver(Elaboratable):
    def __init__(self, pspec):
        # inputs and outputs
        self.pspec = pspec

    def elaborate(self, platform):
        m = Module()
        width = self.pspec.width

        # setup the inputs and outputs of the DUT as anyconst
        a = Signal(width)
        b = Signal(width)
        z = Signal(width)
        opc = Signal(self.pspec.op_wid)
        muxid = Signal(self.pspec.id_wid)
        m.d.comb += [a.eq(AnyConst(width)),
                     b.eq(AnyConst(width)),
                     opc.eq(AnyConst(self.pspec.op_wid)),
                     muxid.eq(AnyConst(self.pspec.id_wid))]

        m.submodules.dut = dut = FPCMPPipeMod(self.pspec)

        # Decode the inputs and outputs so they're easier to work with
        a1 = FPNumBaseRecord(width, False)
        b1 = FPNumBaseRecord(width, False)
        z1 = FPNumBaseRecord(width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        m.submodules.sc_decode_z = z1 = FPNumDecode(None, z1)
        m.d.comb += [a1.v.eq(a),
                     b1.v.eq(b),
                     z1.v.eq(z)]

        m.d.comb += Assert((z1.v == 0) | (z1.v == 1))

        a_lt_b = Signal()

        with m.If(a1.s != b1.s):
            m.d.comb += a_lt_b.eq(a1.s > b1.s)
        with m.Elif(a1.s == 0):
            m.d.comb += a_lt_b.eq(a1.v[0:31] < b1.v[0:31])
        with m.Else():
            m.d.comb += a_lt_b.eq(a1.v[0:31] > b1.v[0:31])


        with m.If(a1.is_nan | b1.is_nan):
            m.d.comb += Assert(z1.v == 0)
        with m.Else():
            with m.Switch(opc):
                with m.Case(0b10):
                    m.d.comb += Assert(z1.v == (a1.v == b1.v))
                with m.Case(0b00):
                    m.d.comb += Assert(z1.v == (a_lt_b))
                with m.Case(0b01):
                    m.d.comb += Assert(z1.v == (a_lt_b |
                                                (a1.v == b1.v)))
            


        # connect up the inputs and outputs.
        m.d.comb += dut.i.a.eq(a)
        m.d.comb += dut.i.b.eq(b)
        m.d.comb += dut.i.ctx.op.eq(opc)
        m.d.comb += dut.i.muxid.eq(muxid)
        m.d.comb += z.eq(dut.o.z)

        return m

    def ports(self):
        return []


class FPCMPTestCase(FHDLTestCase):
    def test_fpcmp(self):
        for bits in [32, 16, 64]:
            module = FPCMPDriver(PipelineSpec(bits, 2, 2))
            self.assertFormal(module, mode="bmc", depth=4)


if __name__ == '__main__':
    unittest.main()

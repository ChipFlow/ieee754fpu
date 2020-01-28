# Proof of correctness for FPMAX module
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable, Mux
from nmigen.asserts import Assert, AnyConst
from nmigen.test.utils import FHDLTestCase

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from ieee754.fpmax.fpmax import FPMAXPipeMod
from ieee754.pipeline import PipelineSpec
import unittest


# This defines a module to drive the device under test and assert
# properties about its outputs
class FPMAXDriver(Elaboratable):
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

        m.submodules.dut = dut = FPMAXPipeMod(self.pspec)

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

        # Since this calculates the min/max of two values, the value
        # it returns should either be one of the two values, or NaN
        m.d.comb += Assert((z1.v == a1.v) | (z1.v == b1.v) |
                           (z1.v == a1.fp.nan2(0)))

        # If both the operands are NaN, max/min should return NaN
        with m.If(a1.is_nan & b1.is_nan):
            m.d.comb += Assert(z1.is_nan)
        # If only one of the operands is NaN, fmax and fmin should
        # return the other operand
        with m.Elif(a1.is_nan & ~b1.is_nan):
            m.d.comb += Assert(z1.v == b1.v)
        with m.Elif(b1.is_nan & ~a1.is_nan):
            m.d.comb += Assert(z1.v == a1.v)
        # If none of the operands are NaN, then compare the values and
        # determine the largest or smallest
        with m.Else():
            # Selects whether the result should be the left hand side
            # (a) or right hand side (b)
            isrhs = Signal()
            # if a1 is negative and b1 isn't, then we should return b1
            with m.If(a1.s != b1.s):
                m.d.comb += isrhs.eq(a1.s > b1.s)
            with m.Else():
                # if they both have the same sign, compare the
                # exponent/mantissa as an integer
                gt = Signal()
                m.d.comb += gt.eq(a[0:width-1] < b[0:width-1])
                # Invert the result we got if both sign bits are set
                # (A bigger exponent/mantissa with a set sign bit
                # means a smaller value)
                m.d.comb += isrhs.eq(gt ^ a1.s)

            with m.If(opc == 0):
                m.d.comb += Assert(z1.v ==
                                   Mux(opc[0] ^ isrhs,
                                       b1.v, a1.v))

        # connect up the inputs and outputs.
        m.d.comb += dut.i.a.eq(a)
        m.d.comb += dut.i.b.eq(b)
        m.d.comb += dut.i.ctx.op.eq(opc)
        m.d.comb += dut.i.muxid.eq(muxid)
        m.d.comb += z.eq(dut.o.z)

        return m

    def ports(self):
        return []


class FPMAXTestCase(FHDLTestCase):
    def test_max(self):
        for bits in [16, 32, 64]:
            module = FPMAXDriver(PipelineSpec(bits, 2, 1))
            self.assertFormal(module, mode="bmc", depth=4)


if __name__ == '__main__':
    unittest.main()

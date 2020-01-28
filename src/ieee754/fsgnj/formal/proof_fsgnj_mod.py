# Proof of correctness for FSGNJ module
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable
from nmigen.asserts import Assert, Assume
from nmigen.test.utils import FHDLTestCase

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from ieee754.fsgnj.fsgnj import FSGNJPipeMod
from ieee754.pipeline import PipelineSpec
import unittest

# This defines a module to drive the device under test and assert
# properties about its outputs
class FSGNJDriver(Elaboratable):
    def __init__(self, pspec):
        # inputs and outputs
        self.pspec = pspec
        self.a = Signal(pspec.width)
        self.b = Signal(pspec.width)
        self.z = Signal(pspec.width)
        self.opc = Signal(pspec.op_wid)
        self.muxid = Signal(pspec.id_wid)

    def elaborate(self, platform):
        m = Module()

        m.submodules.dut = dut = FSGNJPipeMod(self.pspec)

        a1 = FPNumBaseRecord(self.pspec.width, False)
        b1 = FPNumBaseRecord(self.pspec.width, False)
        z1 = FPNumBaseRecord(self.pspec.width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        m.submodules.sc_decode_z = z1 = FPNumDecode(None, z1)

        m.d.comb += [a1.v.eq(self.a),
                     b1.v.eq(self.b),
                     z1.v.eq(self.z)]

        # connect up the inputs and outputs. I think these could
        # theoretically be $anyconst/$anysync but I'm not sure nmigen
        # has support for that
        m.d.comb += dut.i.a.eq(self.a)
        m.d.comb += dut.i.b.eq(self.b)
        m.d.comb += dut.i.ctx.op.eq(self.opc)
        m.d.comb += dut.i.muxid.eq(self.muxid)
        m.d.comb += self.z.eq(dut.o.z)

        # Since the RISCV spec doesn't define what FSGNJ with a funct3
        # field of 0b011 throug 0b111 does, they should be ignored.
        m.d.comb += Assume(self.opc != 0b11)

        # The RISCV spec (page 70) says FSGNJ "produces a result that
        # takes all buts except the sign bit from [operand 1]". This
        # asserts that that holds true
        m.d.comb += Assert(z1.e == a1.e)
        m.d.comb += Assert(z1.m == a1.m)

        with m.Switch(self.opc):

            # The RISCV Spec (page 70) states that for FSGNJ (opcode
            # 0b00 in this case) "the result's sign bit is [operand
            # 2's] sign bit"
            with m.Case(0b00):
                m.d.comb += Assert(z1.s == b1.s)

            # The RISCV Spec (page 70) states that for FSGNJN (opcode
            # 0b01 in this case) "the result's sign bit is the opposite
            # of [operand 2's] sign bit"
            with m.Case(0b01):
                m.d.comb += Assert(z1.s == ~b1.s)
            # The RISCV Spec (page 70) states that for FSGNJX (opcode
            # 0b10 in this case) "the result's sign bit is the XOR of
            # the sign bits of [operand 1] and [operand 2]"
            with m.Case(0b10):
                m.d.comb += Assert(z1.s == (a1.s ^ b1.s))

        return m

    def ports(self):
        return [self.a, self.b, self.z, self.opc, self.muxid]


class FPMAXTestCase(FHDLTestCase):
    def test_max(self):
        for bits in [16, 32, 64]:
            module = FSGNJDriver(PipelineSpec(bits, 2, 2))
            self.assertFormal(module, mode="bmc", depth=4)


if __name__ == '__main__':
    unittest.main()

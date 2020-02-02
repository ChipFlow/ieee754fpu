# IEEE Floating Point Conversion, FSGNJ
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>


from nmigen import Module, Signal, Mux

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.packdata import FPPackData
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord


class FPCMPPipeMod(PipeModBase):
    """
    Floating point comparison: FEQ, FLT, FLE
    Opcodes (funct3):
       - 0b00 - FLE - floating point less than or equal to
       - 0b01 - FLT - floating point less than
       - 0b10 - FEQ - floating equals
    """
    def __init__(self, in_pspec):
        self.in_pspec = in_pspec
        super().__init__(in_pspec, "fpcmp")

    def ispec(self):
        return FPBaseData(self.in_pspec)

    def ospec(self):
        return FPPackData(self.in_pspec)

    def elaborate(self, platform):
        m = Module()

        # useful clarity variables
        comb = m.d.comb
        width = self.pspec.width
        opcode = self.i.ctx.op
        z1 = self.o.z

        a1 = FPNumBaseRecord(width, False)
        b1 = FPNumBaseRecord(width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)

        m.d.comb += [a1.v.eq(self.i.a),
                     b1.v.eq(self.i.b)]

        ab_equal = Signal()
        m.d.comb += ab_equal.eq(a1.v == b1.v)
        contains_nan = Signal()
        m.d.comb += contains_nan.eq(a1.is_nan | b1.is_nan)

        with m.If(contains_nan):
            m.d.comb += z1.eq(0)
        with m.Else():
            with m.Switch(opcode):
                with m.Case(0b10):
                    comb += z1.eq(ab_equal)

        # copy the context (muxid, operator)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

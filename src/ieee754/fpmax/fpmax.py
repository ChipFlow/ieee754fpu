# IEEE Floating Point Conversion, FSGNJ
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>


from nmigen import Module, Signal, Cat, Mux

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.packdata import FPPackData
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord


class FPMAXPipeMod(PipeModBase):
    """ FP Sign injection - replaces operand A's sign bit with one
        generated from operand B

        self.ctx.i.op & 0x3 == 0x0 : Copy sign bit from operand B
        self.ctx.i.op & 0x3 == 0x1 : Copy inverted sign bit from operand B
        self.ctx.i.op & 0x3 == 0x2 : Sign bit is A's sign XOR B's sign
    """
    def __init__(self, in_pspec):
        self.in_pspec = in_pspec
        super().__init__(in_pspec, "fpmax")

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

        has_nan = Signal()
        comb += has_nan.eq(a1.is_nan | b1.is_nan)
        with m.If(has_nan):
            comb += z1.eq(Mux(a1.is_nan, self.i.b, self.i.a))
        with m.Else():
            with m.If(a1.s != b1.s):
                
                comb += z1.eq(Mux(a1.s, self.i.b, self.i.a))
            with m.Else():
                gt = Signal()
                sign = Signal()
                comb += sign.eq(a1.s)
                comb += gt.eq(a1.v > b1.v)
                comb += z1.eq(Mux(gt ^ sign, self.i.a, self.i.b))
                              

        # copy the context (muxid, operator)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

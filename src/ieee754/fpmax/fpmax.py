# IEEE Floating Point Conversion, FSGNJ
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>


from nmigen import Module, Signal, Mux

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

        no_nans = Signal(width)
        some_nans = Signal(width)

        # Handle NaNs
        has_nan = Signal()
        comb += has_nan.eq(a1.is_nan | b1.is_nan)
        both_nan = Signal()
        comb += both_nan.eq(a1.is_nan & b1.is_nan)

        # if(both_nan):
        #     some_nans = NaN - created from scratch
        # else:
        #     some_nans = Mux(a1.is_nan, b, a)
        comb += some_nans.eq(Mux(both_nan,
                                 a1.fp.nan2(0),
                                 Mux(a1.is_nan, self.i.b, self.i.a)))

        # if sign(a) != sign(b):
        #    no_nans = Mux(a1.s ^ opcode[0], b, a)
        signs_different = Signal()
        comb += signs_different.eq(a1.s != b1.s)

        signs_different_value = Signal(width)
        comb += signs_different_value.eq(Mux(a1.s ^ opcode[0],
                                             self.i.b,
                                             self.i.a))

        # else:
        #    if a.v > b.v:
        #        no_nans = Mux(opcode[0], b, a)
        #    else:
        #        no_nans = Mux(opcode[0], a, b)
        gt = Signal()
        sign = Signal()
        signs_same = Signal(width)
        comb += sign.eq(a1.s)
        comb += gt.eq(a1.v > b1.v)
        comb += signs_same.eq(Mux(gt ^ sign ^ opcode[0],
                                  self.i.a, self.i.b))
        comb += no_nans.eq(Mux(signs_different, signs_different_value,
                               signs_same))

        comb += z1.eq(Mux(has_nan, some_nans, no_nans))

        # copy the context (muxid, operator)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

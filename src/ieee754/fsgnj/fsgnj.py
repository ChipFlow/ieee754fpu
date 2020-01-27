# IEEE Floating Point Conversion, FSGNJ
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>


from nmigen import Module, Signal, Cat

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.packdata import FPPackData
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord


class FSGNJPipeMod(PipeModBase):
    """ FP Sign injection - replaces operand A's sign bit with one
        generated from operand B

        self.ctx.i.op & 0x3 == 0x0 : Copy sign bit from operand B
        self.ctx.i.op & 0x3 == 0x1 : Copy inverted sign bit from operand B
        self.ctx.i.op & 0x3 == 0x2 : Sign bit is A's sign XOR B's sign
    """
    def __init__(self, in_pspec):
        self.in_pspec = in_pspec
        super().__init__(in_pspec, "fsgnj")

    def ispec(self):
        return FPBaseData(self.in_pspec)

    def ospec(self):
        return FPPackData(self.in_pspec)

    def elaborate(self, platform):
        m = Module()

        width = self.pspec.width
        comb = m.d.comb

        z1 = self.o.z
        a = self.i.a
        b = self.i.b
        a1 = FPNumBaseRecord(width, False)
        b1 = FPNumBaseRecord(width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        comb += [a1.v.eq(self.i.a),
                 b1.v.eq(self.i.b)]

        opcode = self.i.ctx.op

        sign = Signal()

        with m.Switch(opcode):
            with m.Case(0b00):
                comb += sign.eq(b1.s)
            with m.Case(0b01):
                comb += sign.eq(~b1.s)
            with m.Case(0b10):
                comb += sign.eq(a1.s ^ b1.s)
            with m.Default():
                comb += sign.eq(b1.s)

        comb += z1.eq(a1.fp.create2(sign, a1.e, a1.m))

        # copy the context (muxid, operator)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

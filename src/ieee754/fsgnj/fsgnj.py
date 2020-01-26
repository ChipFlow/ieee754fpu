# IEEE Floating Point Conversion
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

from nmigen import Module, Signal, Cat, Mux
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.postcalc import FPPostCalcData
from ieee754.fpcommon.packdata import FPPackData

from ieee754.fpcommon.fpbase import FPNumBaseRecord


class FSGNJPipeMod(PipeModBase):
    """ FP Sign injection - replaces operand A's sign bit with one generated from operand B

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
        comb = m.d.comb

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        z1 = self.o.z
        a = self.i.a
        b = self.i.b

        opcode = self.i.ctx.op

        sign = Signal()

        with m.Switch(opcode):
            with m.Case(0b00):
                comb += sign.eq(b[31])
            with m.Case(0b01):
                comb += sign.eq(~b[31])
            with m.Case(0b10):
                comb += sign.eq(a[31] ^ b[31])

        comb += z1.eq(Cat(a[0:31], sign))


        # copy the context (muxid, operator)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

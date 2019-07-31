# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal
from nmigen.cli import main, verilog

from nmutil.pipemodbase import FPModBase
from ieee754.fpcommon.fpbase import FPNumBase, FPNumBaseRecord
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpcommon.postnormalise import FPNorm1Data


class FPRoundData:

    def __init__(self, pspec):
        width = pspec.width
        self.z = FPNumBaseRecord(width, False, name="z")
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid
        # pipeline bypass [data comes from specialcases]
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

    def eq(self, i):
        ret = [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
               self.ctx.eq(i.ctx)]
        return ret


class FPRoundMod(FPModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "roundz")

    def ispec(self):
        return FPNorm1Data(self.pspec)

    def ospec(self):
        return FPRoundData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        comb += self.o.eq(self.i)  # copies muxid, z, out_do_z
        with m.If(~self.i.out_do_z):  # bypass wasn't enabled
            with m.If(self.i.roundz):
                comb += self.o.z.m.eq(self.i.z.m + 1)  # mantissa up
                with m.If(self.i.z.m == self.i.z.m1s):  # all 1s
                    # exponent up
                    comb += self.o.z.e.eq(self.i.z.e + 1)

        return m

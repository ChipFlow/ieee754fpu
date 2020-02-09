# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Mux
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
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


class FPRoundMod(PipeModBase):

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
        im = self.i.z.m
        ie = self.i.z.e
        msb1s = Signal(reset_less=True)
        comb += msb1s.eq(self.i.z.m.all())  # all 1s
        comb += self.o.z.m.eq(Mux(self.i.roundz, im+1, im))  # mantissa up
        comb += self.o.z.e.eq(Mux(msb1s & self.i.roundz, ie + 1, ie)) # exp up

        return m

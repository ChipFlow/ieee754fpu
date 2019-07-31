# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.fpbase import FPNumBaseRecord, FPNumBase
from ieee754.fpcommon.roundz import FPRoundData
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpcommon.packdata import FPPackData


class FPPackMod(PipeModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "pack")

    def ispec(self):
        return FPRoundData(self.pspec)

    def ospec(self):
        return FPPackData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        z = FPNumBaseRecord(self.pspec.width, False, name="z")
        m.submodules.pack_in_z = in_z = FPNumBase(self.i.z)

        with m.If(~self.i.out_do_z):
            with m.If(in_z.is_overflowed):
                comb += z.inf(self.i.z.s)
            with m.Else():
                comb += z.create(self.i.z.s, self.i.z.e, self.i.z.m)
        with m.Else():
            comb += z.v.eq(self.i.oz)

        comb += self.o.ctx.eq(self.i.ctx)
        comb += self.o.z.eq(z.v)

        return m

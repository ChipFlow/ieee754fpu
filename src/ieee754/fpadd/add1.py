"""IEEE754 Floating Point Multiplier Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Signal
from nmigen.cli import main, verilog
from math import log

from nmutil.pipemodbase import FPModBase
from ieee754.fpcommon.postcalc import FPAddStage1Data
from ieee754.fpadd.add0 import FPAddStage0Data


class FPAddStage1Mod(FPModBase):
    """ Second stage of add: preparation for normalisation.
        detects when tot sum is too big (tot[27] is kinda a carry bit)
    """

    def __init__(self, pspec):
        super().__init__(pspec, "add1")

    def ispec(self):
        return FPAddStage0Data(self.pspec)

    def ospec(self):
        return FPAddStage1Data(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        comb += self.o.z.eq(self.i.z)
        # tot[-1] (MSB) gets set when the sum overflows. shift result down
        with m.If(~self.i.out_do_z):
            with m.If(self.i.tot[-1]):
                comb += [
                    self.o.z.m.eq(self.i.tot[4:]),
                    self.o.of.m0.eq(self.i.tot[4]),
                    self.o.of.guard.eq(self.i.tot[3]),
                    self.o.of.round_bit.eq(self.i.tot[2]),
                    self.o.of.sticky.eq(self.i.tot[1] | self.i.tot[0]),
                    self.o.z.e.eq(self.i.z.e + 1)
            ]
            # tot[-1] (MSB) zero case
            with m.Else():
                comb += [
                    self.o.z.m.eq(self.i.tot[3:]),
                    self.o.of.m0.eq(self.i.tot[3]),
                    self.o.of.guard.eq(self.i.tot[2]),
                    self.o.of.round_bit.eq(self.i.tot[1]),
                    self.o.of.sticky.eq(self.i.tot[0])
            ]

        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.oz.eq(self.i.oz)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

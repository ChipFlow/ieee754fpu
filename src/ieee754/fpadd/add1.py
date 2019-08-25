"""IEEE754 Floating Point Multiplier Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Signal, Mux, Cat
from nmigen.cli import main, verilog
from math import log

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.postcalc import FPPostCalcData
from ieee754.fpadd.add0 import FPAddStage0Data


class FPAddStage1Mod(PipeModBase):
    """ Second stage of add: preparation for normalisation.
        detects when tot sum is too big (tot[27] is kinda a carry bit)

        if sum is too big (MSB is set), the mantissa needs shifting
        down and the exponent increased by 1.

        we also need to extract the overflow info: sticky "accumulates"
        the bottom 2 LSBs if the shift occurs.
    """

    def __init__(self, pspec):
        super().__init__(pspec, "add1")

    def ispec(self):
        return FPAddStage0Data(self.pspec)

    def ospec(self):
        return FPPostCalcData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        z = self.i.z
        tot = self.i.tot

        # intermediaries
        msb = Signal(reset_less=True)
        to = Signal.like(self.i.tot, reset_less=True)

        comb += self.o.z.s.eq(z.s) # copy sign
        comb += msb.eq(self.i.tot[-1]) # get mantissa MSB

        # mantissa shifted down, exponent increased - if MSB set
        comb += self.o.z.e.eq(Mux(msb, z.e + 1, z.e))
        comb += to.eq(Mux(msb, Cat(tot, 0), Cat(0, tot)))

        # this works by adding an extra zero LSB if the MSB is *not* set
        comb += [
            self.o.z.m.eq(to[4:]),
            self.o.of.m0.eq(to[4]),
            self.o.of.guard.eq(to[3]),
            self.o.of.round_bit.eq(to[2]),
            # sticky sourced from LSB and shifted if MSB hi, else unshifted
            self.o.of.sticky.eq(Mux(msb, to[1] | tot[0], to[1]))
        ]

        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.oz.eq(self.i.oz)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

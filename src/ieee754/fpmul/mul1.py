"""IEEE754 Floating Point Multiplier Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.postcalc import FPAddStage1Data
from ieee754.fpmul.mul0 import FPMulStage0Data


class FPMulStage1Mod(Elaboratable):
    """ Second stage of mul: preparation for normalisation.
    """

    def __init__(self, pspec):
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPMulStage0Data(self.pspec)

    def ospec(self):
        return FPAddStage1Data(self.pspec)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.mul1 = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.z.eq(self.i.z)
        with m.If(~self.i.out_do_z):
            # results are in the range 0.25 to 0.999999999999
            # sometimes the MSB will be zero, (0.5 * 0.5 = 0.25 which
            # in binary is 0b010000) so to compensate for that we have
            # to shift the mantissa up (and reduce the exponent by 1)
            p = Signal(len(self.i.product), reset_less=True)
            with m.If(self.i.product[-1]):
                m.d.comb += p.eq(self.i.product)
            with m.Else():
                # get 1 bit of extra accuracy if the mantissa top bit is zero
                m.d.comb += p.eq(self.i.product<<1)
                m.d.comb += self.o.z.e.eq(self.i.z.e-1)

            # top bits are mantissa, then guard and round, and the rest of
            # the product is sticky
            mw = self.o.z.m_width
            m.d.comb += [
                self.o.z.m.eq(p[mw+2:]),            # mantissa
                self.o.of.m0.eq(p[mw+2]),           # copy of LSB
                self.o.of.guard.eq(p[mw+1]),        # guard
                self.o.of.round_bit.eq(p[mw]),      # round
                self.o.of.sticky.eq(p[0:mw].bool()) # sticky
            ]

        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m

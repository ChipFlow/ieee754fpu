"""IEEE754 Floating Point Library

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module
from nmigen.cli import main, verilog
from math import log

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.fpbase import FPNumBase
from ieee754.fpcommon.pscdata import FPSCData


class FPAddDeNormMod(PipeModBase):

    def __init__(self, pspec, m_extra):
        self.m_extra = m_extra
        super().__init__(pspec, "denormalise")

    def ispec(self):
        return FPSCData(self.pspec, self.m_extra)

    def ospec(self):
        return FPSCData(self.pspec, self.m_extra)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        m.submodules.denorm_in_a = in_a = FPNumBase(self.i.a)
        m.submodules.denorm_in_b = in_b = FPNumBase(self.i.b)

        with m.If(~self.i.out_do_z):
            # XXX hmmm, don't like repeating identical code
            comb += self.o.a.eq(self.i.a)
            with m.If(in_a.exp_n127):
                comb += self.o.a.e.eq(self.i.a.N126)  # limit a exponent
            with m.Else():
                comb += self.o.a.m[-1].eq(1)  # set top mantissa bit

            comb += self.o.b.eq(self.i.b)
            with m.If(in_b.exp_n127):
                comb += self.o.b.e.eq(self.i.b.N126)  # limit a exponent
            with m.Else():
                comb += self.o.b.m[-1].eq(1)  # set top mantissa bit

        comb += self.o.ctx.eq(self.i.ctx)
        comb += self.o.z.eq(self.i.z)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.oz.eq(self.i.oz)

        return m

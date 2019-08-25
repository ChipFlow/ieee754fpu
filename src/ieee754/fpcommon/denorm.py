"""IEEE754 Floating Point Library

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Mux
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

        # XXX hmmm, don't like repeating identical code
        comb += self.o.a.eq(self.i.a)
        ae = self.i.a.e
        am = self.i.a.m
        # either limit exponent, or set top mantissa bit
        comb += self.o.a.e.eq(Mux(in_a.exp_n127, self.i.a.N126, ae))
        comb += self.o.a.m[-1].eq(Mux(in_a.exp_n127, am[-1], 1))

        # XXX code now repeated for b
        comb += self.o.b.eq(self.i.b)
        be = self.i.b.e
        bm = self.i.b.m
        # either limit exponent, or set top mantissa bit
        comb += self.o.b.e.eq(Mux(in_b.exp_n127, self.i.b.N126, be))
        comb += self.o.b.m[-1].eq(Mux(in_b.exp_n127, bm[-1], 1))

        comb += self.o.ctx.eq(self.i.ctx)
        comb += self.o.z.eq(self.i.z)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.oz.eq(self.i.oz)

        return m

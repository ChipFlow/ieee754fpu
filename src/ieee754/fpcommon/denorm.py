# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.modbase import FPModBase
from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.fpbase import FPNumBase
from ieee754.fpcommon.getop import FPPipeContext


class FPSCData:

    def __init__(self, pspec, m_extra):
        width = pspec.width
        # NOTE: difference between z and oz is that oz is created by
        # special-cases module(s) and will propagate, along with its
        # "bypass" signal out_do_z, through the pipeline, *disabling*
        # all processing of all subsequent stages.
        self.a = FPNumBaseRecord(width, m_extra, name="a")   # operand a
        self.b = FPNumBaseRecord(width, m_extra, name="b")   # operand b
        self.z = FPNumBaseRecord(width, False, name="z")     # denormed result
        self.oz = Signal(width, reset_less=True)   # "finished" (bypass) result
        self.out_do_z = Signal(reset_less=True)    # "bypass" enabled
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid

    def __iter__(self):
        yield from self.a
        yield from self.b
        yield from self.z
        yield self.oz
        yield self.out_do_z
        yield from self.ctx

    def eq(self, i):
        ret = [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
               self.a.eq(i.a), self.b.eq(i.b), self.ctx.eq(i.ctx)]
        return ret


class FPAddDeNormMod(FPModBase):

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



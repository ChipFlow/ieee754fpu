# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import FPNumIn, FPNumOut, FPNumBaseRecord
from ieee754.fpcommon.fpbase import FPState, FPNumBase
from ieee754.fpcommon.getop import FPBaseData


class FPSCData:

    def __init__(self, width, pspec, m_extra):

        # NOTE: difference between z and oz is that oz is created by
        # special-cases module(s) and will propagate, along with its
        # "bypass" signal out_do_z, through the pipeline, *disabling*
        # all processing of all subsequent stages.
        self.a = FPNumBaseRecord(width, m_extra)   # operand a
        self.b = FPNumBaseRecord(width, m_extra)   # operand b
        self.z = FPNumBaseRecord(width, False)     # denormed result 
        self.oz = Signal(width, reset_less=True)   # "finished" (bypass) result
        self.out_do_z = Signal(reset_less=True)    # "bypass" enabled
        self.ctx = FPBaseData(width, pspec) 
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


class FPAddDeNormMod(FPState, Elaboratable):

    def __init__(self, width, pspec, m_extra):
        self.width = width
        self.pspec = pspec
        self.m_extra = m_extra
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.pspec, self.m_extra)

    def ospec(self):
        return FPSCData(self.width, self.pspec, self.m_extra)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.denormalise = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.submodules.denorm_in_a = in_a = FPNumBase(self.i.a)
        m.submodules.denorm_in_b = in_b = FPNumBase(self.i.b)
        #m.submodules.denorm_out_a = self.o.a
        #m.submodules.denorm_out_b = self.o.b
        #m.submodules.denorm_out_z = self.o.z

        with m.If(~self.i.out_do_z):
            # XXX hmmm, don't like repeating identical code
            m.d.comb += self.o.a.eq(self.i.a)
            with m.If(in_a.exp_n127):
                m.d.comb += self.o.a.e.eq(self.i.a.N126) # limit a exponent
            with m.Else():
                m.d.comb += self.o.a.m[-1].eq(1) # set top mantissa bit

            m.d.comb += self.o.b.eq(self.i.b)
            with m.If(in_b.exp_n127):
                m.d.comb += self.o.b.e.eq(self.i.b.N126) # limit a exponent
            with m.Else():
                m.d.comb += self.o.b.m[-1].eq(1) # set top mantissa bit

        m.d.comb += self.o.ctx.eq(self.i.ctx)
        m.d.comb += self.o.z.eq(self.i.z)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)

        return m


class FPAddDeNorm(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "denormalise")
        self.mod = FPAddDeNormMod(width)
        self.out_a = FPNumBaseRecord(width)
        self.out_b = FPNumBaseRecord(width)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        m.d.sync += self.out_a.eq(self.mod.out_a)
        m.d.sync += self.out_b.eq(self.mod.out_b)

    def action(self, m):
        # Denormalised Number checks
        m.next = "align"



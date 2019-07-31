# IEEE Floating Point Multiplier

from nmigen import Module, Signal, Cat, Mux
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.modbase import FPModBase
from ieee754.fpcommon.fpbase import FPNumBase
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpcommon.msbhigh import FPMSBHigh
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPAddStage1Data


class FPAlignModSingle(FPModBase):

    def __init__(self, pspec, e_extra=False):
        self.e_extra = e_extra
        super().__init__(pspec, "align")

    def ispec(self):
        return FPSCData(self.pspec, False)

    def ospec(self):
        return FPSCData(self.pspec, False)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        self.o.a.m.name = "o_a_m"
        self.o.b.m.name = "o_b_m"

        m.submodules.norm1_insel_a = insel_a = FPNumBase(self.i.a)
        m.submodules.norm1_insel_b = insel_b = FPNumBase(self.i.b)
        insel_a.m.name = "i_a_m"
        insel_b.m.name = "i_b_m"

        mwid = self.o.z.m_width
        msb_a = FPMSBHigh(mwid, len(insel_a.e))
        msb_b = FPMSBHigh(mwid, len(insel_b.e))
        m.submodules.norm_pe_a = msb_a
        m.submodules.norm_pe_b = msb_b

        # connect to msb_a/b module
        comb += msb_a.m_in.eq(insel_a.m)
        comb += msb_a.e_in.eq(insel_a.e)
        comb += msb_b.m_in.eq(insel_b.m)
        comb += msb_b.e_in.eq(insel_b.e)

        # copy input to output (overridden below)
        comb += self.o.a.eq(insel_a)
        comb += self.o.b.eq(insel_b)

        # normalisation increase/decrease conditions
        decrease_a = Signal(reset_less=True)
        decrease_b = Signal(reset_less=True)
        comb += decrease_a.eq(insel_a.m_msbzero)
        comb += decrease_b.eq(insel_b.m_msbzero)

        # ok this is near-identical to FPNorm: use same class (FPMSBHigh)
        with m.If(~self.i.out_do_z):
            with m.If(decrease_a):
                comb += [
                    self.o.a.e.eq(msb_a.e_out),
                    self.o.a.m.eq(msb_a.m_out),
                ]
            with m.If(decrease_b):
                comb += [
                    self.o.b.e.eq(msb_b.e_out),
                    self.o.b.m.eq(msb_b.m_out),
                ]

        comb += self.o.ctx.eq(self.i.ctx)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.oz.eq(self.i.oz)

        return m

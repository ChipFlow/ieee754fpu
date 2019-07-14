# IEEE Floating Point Multiplier

from nmigen import Module, Signal, Cat, Mux, Elaboratable
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from nmutil.singlepipe import (StageChain, SimpleHandshake)

from ieee754.fpcommon.fpbase import (Overflow, OverflowMod,
                                     FPNumBase, FPNumBaseRecord)
from ieee754.fpcommon.fpbase import MultiShiftRMerge
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.getop import FPPipeContext


from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPAddStage1Data


class FPAlignModSingle(Elaboratable):

    def __init__(self, pspec, e_extra=False):
        self.pspec = pspec
        self.e_extra = e_extra
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPSCData(self.pspec, False)

    def ospec(self):
        return FPSCData(self.pspec, False)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.align = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        mwid = self.o.z.m_width
        pe_a = PriorityEncoder(mwid)
        pe_b = PriorityEncoder(mwid)
        m.submodules.norm_pe_a = pe_a
        m.submodules.norm_pe_b = pe_b

        self.o.a.m.name = "o_a_m"
        self.o.b.m.name = "o_b_m"

        m.submodules.norm1_insel_a = insel_a = FPNumBase(self.i.a)
        m.submodules.norm1_insel_b = insel_b = FPNumBase(self.i.b)
        insel_a.m.name = "i_a_m"
        insel_b.m.name = "i_b_m"

        # copy input to output (overridden below)
        m.d.comb += self.o.a.eq(insel_a)
        m.d.comb += self.o.b.eq(insel_b)

        # normalisation increase/decrease conditions
        decrease_a = Signal(reset_less=True)
        decrease_b = Signal(reset_less=True)
        m.d.comb += decrease_a.eq(insel_a.m_msbzero)
        m.d.comb += decrease_b.eq(insel_b.m_msbzero)

        # ok this is near-identical to FPNorm.  TODO: modularise
        with m.If(~self.i.out_do_z):
            with m.If(decrease_a):
                # *sigh* not entirely obvious: count leading zeros (clz)
                # with a PriorityEncoder: to find from the MSB
                # we reverse the order of the bits.
                temp_a = Signal(mwid, reset_less=True)
                clz_a = Signal((len(insel_a.e), True), reset_less=True)
                m.d.comb += [
                    pe_a.i.eq(insel_a.m[::-1]),      # inverted
                    clz_a.eq(pe_a.o),                # count zeros from MSB down
                    temp_a.eq((insel_a.m << clz_a)), # shift mantissa UP
                    self.o.a.e.eq(insel_a.e - clz_a), # DECREASE exponent
                    self.o.a.m.eq(temp_a),
                ]

            with m.If(decrease_b):
                # *sigh* not entirely obvious: count leading zeros (clz)
                # with a PriorityEncoder: to find from the MSB
                # we reverse the order of the bits.
                temp_b = Signal(mwid, reset_less=True)
                clz_b = Signal((len(insel_b.e), True), reset_less=True)
                m.d.comb += [
                    pe_b.i.eq(insel_b.m[::-1]),      # inverted
                    clz_b.eq(pe_b.o),                # count zeros from MSB down
                    temp_b.eq((insel_b.m << clz_b)), # shift mantissa UP
                    self.o.b.e.eq(insel_b.e - clz_b), # DECREASE exponent
                    self.o.b.m.eq(temp_b),
                ]

        m.d.comb += self.o.ctx.eq(self.i.ctx)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)

        return m



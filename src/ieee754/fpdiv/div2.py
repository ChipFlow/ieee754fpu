"""IEEE Floating Point Divider

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99
"""

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.postcalc import FPAddStage1Data
from .div0 import FPDivStage0Data # XXX TODO: replace


class FPDivStage2Mod(FPState, Elaboratable):
    """ Second stage of div: preparation for normalisation.
    """

    def __init__(self, pspec):
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return DivPipeOutputData(self.pspec) # Q/Rem in...

    def ospec(self):
        # XXX REQUIRED.  MUST NOT BE CHANGED.  this is the format
        # required for ongoing processing (normalisation, correction etc.)
        return FPAddStage1Data(self.pspec) # out to post-process

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.div1 = self
        #m.submodules.div1_out_overflow = self.o.of

        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()

        # copies sign and exponent and mantissa (mantissa to be overridden
        # below)
        m.d.comb += self.o.z.eq(self.i.z)

        # TODO: this is "phase 3" of divide (the very end of the pipeline)
        # takes the Q and R data (whatever) and performs
        # last-stage guard/round/sticky and copies mantissa into z.
        # post-processing stages take care of things from that point.

        # NOTE: this phase does NOT do ACTUAL DIV processing, it ONLY
        # does "conversion" *out* of the Q/REM last stage

        with m.If(~self.i.out_do_z):
            mw = self.o.z.m_width
            m.d.comb += [
                self.o.z.m.eq(self.i.quotient_root[mw+2:]),
                self.o.of.m0.eq(self.i.quotient_root[mw+2]), # copy of LSB
                self.o.of.guard.eq(self.i.quotient_root[mw+1]),
                self.o.of.round_bit.eq(self.i.quotient_root[mw]),
                self.o.of.sticky.eq(Cat(self.i.remainder,
                                        self.i.quotient_root[:mw]).bool())
            ]

        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPDivStage2(FPState):

    def __init__(self, pspec):
        FPState.__init__(self, "divider_1")
        self.mod = FPDivStage2Mod(pspec)
        self.out_z = FPNumBaseRecord(pspec, False)
        self.out_of = Overflow()
        self.norm_stb = Signal()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        m.d.sync += self.norm_stb.eq(0) # sets to zero when not in div1 state

        m.d.sync += self.out_of.eq(self.mod.out_of)
        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.norm_stb.eq(1)

    def action(self, m):
        m.next = "normalise_1"


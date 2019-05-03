# IEEE Floating Point Multiplier

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.postcalc import FPAddStage1Data
from .mul0 import FPMulStage0Data


class FPMulStage1Mod(FPState, Elaboratable):
    """ Second stage of mul: preparation for normalisation.
    """

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPMulStage0Data(self.width, self.id_wid)

    def ospec(self):
        return FPAddStage1Data(self.width, self.id_wid)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.mul1 = self
        m.submodules.mul1_out_overflow = self.o.of

        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.z.eq(self.i.z)
        with m.If(~self.i.out_do_z):
            mw = self.o.z.m_width
            m.d.comb += [
                self.o.z.m.eq(self.i.product[mw+2:]),
                self.o.of.m0.eq(self.i.product[mw+2]),
                self.o.of.guard.eq(self.i.product[mw+1]),
                self.o.of.round_bit.eq(self.i.product[mw]),
                self.o.of.sticky.eq(self.i.product[0:mw].bool())
            ]

        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.mid.eq(self.i.mid)

        return m


class FPMulStage1(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "multiply_1")
        self.mod = FPMulStage1Mod(width)
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()
        self.norm_stb = Signal()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        m.d.sync += self.norm_stb.eq(0) # sets to zero when not in mul1 state

        m.d.sync += self.out_of.eq(self.mod.out_of)
        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.norm_stb.eq(1)

    def action(self, m):
        m.next = "normalise_1"


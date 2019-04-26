# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog
from math import log

from fpbase import FPState
from fpcommon.postcalc import FPAddStage1Data
from fpadd.add0 import FPAddStage0Data


class FPAddStage1Mod(FPState, Elaboratable):
    """ Second stage of add: preparation for normalisation.
        detects when tot sum is too big (tot[27] is kinda a carry bit)
    """

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPAddStage0Data(self.width, self.id_wid)

    def ospec(self):
        return FPAddStage1Data(self.width, self.id_wid)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.add1 = self
        m.submodules.add1_out_overflow = self.o.of

        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.z.eq(self.i.z)
        # tot[-1] (MSB) gets set when the sum overflows. shift result down
        with m.If(~self.i.out_do_z):
            with m.If(self.i.tot[-1]):
                m.d.comb += [
                    self.o.z.m.eq(self.i.tot[4:]),
                    self.o.of.m0.eq(self.i.tot[4]),
                    self.o.of.guard.eq(self.i.tot[3]),
                    self.o.of.round_bit.eq(self.i.tot[2]),
                    self.o.of.sticky.eq(self.i.tot[1] | self.i.tot[0]),
                    self.o.z.e.eq(self.i.z.e + 1)
            ]
            # tot[-1] (MSB) zero case
            with m.Else():
                m.d.comb += [
                    self.o.z.m.eq(self.i.tot[3:]),
                    self.o.of.m0.eq(self.i.tot[3]),
                    self.o.of.guard.eq(self.i.tot[2]),
                    self.o.of.round_bit.eq(self.i.tot[1]),
                    self.o.of.sticky.eq(self.i.tot[0])
            ]

        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.mid.eq(self.i.mid)

        return m


class FPAddStage1(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "add_1")
        self.mod = FPAddStage1Mod(width)
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()
        self.norm_stb = Signal()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        m.d.sync += self.norm_stb.eq(0) # sets to zero when not in add1 state

        m.d.sync += self.out_of.eq(self.mod.out_of)
        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.norm_stb.eq(1)

    def action(self, m):
        m.next = "normalise_1"


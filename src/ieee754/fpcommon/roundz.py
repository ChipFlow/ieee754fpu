# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPNumBase
from ieee754.fpcommon.fpbase import FPState
from .postnormalise import FPNorm1Data


class FPRoundData:

    def __init__(self, width, id_wid):
        self.z = FPNumBase(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.mid.eq(i.mid)]


class FPRoundMod(Elaboratable):

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.out_z = self.ospec()

    def ispec(self):
        return FPNorm1Data(self.width, self.id_wid)

    def ospec(self):
        return FPRoundData(self.width, self.id_wid)

    def process(self, i):
        return self.out_z

    def setup(self, m, i):
        m.submodules.roundz = self
        m.submodules.round_out_z = self.i.z
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.out_z.eq(self.i) # copies mid, z, out_do_z
        with m.If(~self.i.out_do_z):
            with m.If(self.i.roundz):
                m.d.comb += self.out_z.z.m.eq(self.i.z.m + 1) # mantissa up
                with m.If(self.i.z.m == self.i.z.m1s): # all 1s
                    m.d.comb += self.out_z.z.e.eq(self.i.z.e + 1) # exponent up

        return m


class FPRound(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "round")
        self.mod = FPRoundMod(width)
        self.out_z = self.ospec()

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        self.idsync(m)
        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.out_z.mid.eq(self.mod.o.mid)

    def action(self, m):
        m.next = "corrections"

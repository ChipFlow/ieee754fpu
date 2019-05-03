# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Elaboratable
from nmigen.cli import main, verilog
from ieee754.fpcommon.fpbase import FPState
from .roundz import FPRoundData


class FPCorrectionsMod(Elaboratable):

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.out_z = self.ospec()

    def ispec(self):
        return FPRoundData(self.width, self.id_wid)

    def ospec(self):
        return FPRoundData(self.width, self.id_wid)

    def process(self, i):
        return self.out_z

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.corrections = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.submodules.corr_in_z = self.i.z
        m.submodules.corr_out_z = self.out_z.z
        m.d.comb += self.out_z.eq(self.i) # copies mid, z, out_do_z
        with m.If(~self.i.out_do_z):
            with m.If(self.i.z.is_denormalised):
                m.d.comb += self.out_z.z.e.eq(self.i.z.N127)
        return m


class FPCorrections(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "corrections")
        self.mod = FPCorrectionsMod(width)
        self.out_z = self.ospec()

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z)

        m.d.sync += self.out_z.eq(self.mod.out_z)
        m.d.sync += self.out_z.mid.eq(self.mod.o.mid)

    def action(self, m):
        m.next = "pack"


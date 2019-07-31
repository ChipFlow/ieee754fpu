# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module
from nmigen.cli import main, verilog

from ieee754.fpcommon.modbase import FPModBase
from ieee754.fpcommon.fpbase import FPNumBase
from ieee754.fpcommon.roundz import FPRoundData


class FPCorrectionsMod(FPModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "corrections")

    def ispec(self):
        return FPRoundData(self.pspec)

    def ospec(self):
        return FPRoundData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        m.submodules.corr_in_z = in_z = FPNumBase(self.i.z)
        m.d.comb += self.o.eq(self.i) # copies mid, z, out_do_z
        with m.If(~self.i.out_do_z):
            with m.If(in_z.is_denormalised):
                m.d.comb += self.o.z.e.eq(self.i.z.N127)
        return m



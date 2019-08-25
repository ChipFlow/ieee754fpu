# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Mux
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.fpbase import FPNumBase
from ieee754.fpcommon.roundz import FPRoundData


class FPCorrectionsMod(PipeModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "corrections")

    def ispec(self):
        return FPRoundData(self.pspec)

    def ospec(self):
        return FPRoundData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        m.submodules.corr_in_z = in_z = FPNumBase(self.i.z)
        comb += self.o.eq(self.i) # copies mid, z, out_do_z
        comb += self.o.z.e.eq(Mux(in_z.is_denormalised,
                                  self.i.z.N127, self.i.z.e))
        return m



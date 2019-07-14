# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPNumBase, FPNumBaseRecord
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.getop import FPPipeContext
from .postnormalise import FPNorm1Data


class FPRoundData:

    def __init__(self, pspec):
        width = pspec.width
        self.z = FPNumBaseRecord(width, False)
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid
        # pipeline bypass [data comes from specialcases]
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

    def eq(self, i):
        ret = [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
               self.ctx.eq(i.ctx)]
        return ret


class FPRoundMod(Elaboratable):

    def __init__(self, pspec):
        self.pspec = pspec
        self.i = self.ispec()
        self.out_z = self.ospec()

    def ispec(self):
        return FPNorm1Data(self.pspec)

    def ospec(self):
        return FPRoundData(self.pspec)

    def process(self, i):
        return self.out_z

    def setup(self, m, i):
        m.submodules.roundz = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.out_z.eq(self.i)  # copies muxid, z, out_do_z
        with m.If(~self.i.out_do_z):  # bypass wasn't enabled
            with m.If(self.i.roundz):
                m.d.comb += self.out_z.z.m.eq(self.i.z.m + 1)  # mantissa up
                with m.If(self.i.z.m == self.i.z.m1s):  # all 1s
                    # exponent up
                    m.d.comb += self.out_z.z.e.eq(self.i.z.e + 1)

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
        m.d.sync += self.out_z.ctx.eq(self.mod.o.ctx)

    def action(self, m):
        m.next = "corrections"

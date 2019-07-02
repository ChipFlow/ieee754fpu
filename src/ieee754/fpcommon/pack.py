# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPNumOut, FPNumBaseRecord, FPNumBase
from ieee754.fpcommon.fpbase import FPState
from .roundz import FPRoundData
from nmutil.singlepipe import Object
from ieee754.fpcommon.getop import FPBaseData


class FPPackData(Object):

    def __init__(self, width, pspec):
        Object.__init__(self)
        self.z = Signal(width, reset_less=True)    # result
        self.ctx = FPBaseData(width, pspec)
        self.mid = self.ctx.mid

class FPPackMod(Elaboratable):

    def __init__(self, width, pspec):
        self.width = width
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPRoundData(self.width, self.pspec)

    def ospec(self):
        return FPPackData(self.width, self.pspec)

    def process(self, i):
        return self.o

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        m.submodules.pack = self
        m.d.comb += self.i.eq(in_z)

    def elaborate(self, platform):
        m = Module()
        z = FPNumBaseRecord(self.width, False)
        m.submodules.pack_in_z = in_z = FPNumBase(self.i.z)
        #m.submodules.pack_out_z = out_z = FPNumOut(z)
        m.d.comb += self.o.ctx.eq(self.i.ctx)
        with m.If(~self.i.out_do_z):
            with m.If(in_z.is_overflowed):
                m.d.comb += z.inf(self.i.z.s)
            with m.Else():
                m.d.comb += z.create(self.i.z.s, self.i.z.e, self.i.z.m)
        with m.Else():
            m.d.comb += z.v.eq(self.i.oz)
        m.d.comb += self.o.z.eq(z.v)
        return m


class FPPack(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "pack")
        self.mod = FPPackMod(width)
        self.out_z = self.ospec()

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z)

        m.d.sync += self.out_z.v.eq(self.mod.out_z.v)
        m.d.sync += self.out_z.ctx.eq(self.mod.o.ctx)

    def action(self, m):
        m.next = "pack_put_z"

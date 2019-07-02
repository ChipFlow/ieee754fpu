# IEEE Floating Point Muler (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext


class FPMulStage0Data:

    def __init__(self, width, pspec):
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        mw = (self.z.m_width)*2 - 1 + 3 # sticky/round/guard bits + (2*mant) - 1
        self.product = Signal(mw, reset_less=True)
        self.ctx = FPPipeContext(width, pspec)
        self.muxid = self.ctx.muxid

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.product.eq(i.product), self.ctx.eq(i.ctx)]


class FPMulStage0Mod(Elaboratable):

    def __init__(self, width, pspec):
        self.width = width
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.pspec, False)

    def ospec(self):
        return FPMulStage0Data(self.width, self.pspec)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.mul0 = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        #m.submodules.mul0_in_a = self.i.a
        #m.submodules.mul0_in_b = self.i.b
        #m.submodules.mul0_out_z = self.o.z

        # store intermediate tests (and zero-extended mantissas)
        am0 = Signal(len(self.i.a.m)+1, reset_less=True)
        bm0 = Signal(len(self.i.b.m)+1, reset_less=True)
        m.d.comb += [
                     am0.eq(Cat(self.i.a.m, 0)),
                     bm0.eq(Cat(self.i.b.m, 0))
                    ]
        # same-sign (both negative or both positive) mul mantissas
        with m.If(~self.i.out_do_z):
            m.d.comb += [self.o.z.e.eq(self.i.a.e + self.i.b.e + 1),
                         self.o.product.eq(am0 * bm0 * 4),
                         self.o.z.s.eq(self.i.a.s ^ self.i.b.s)
                ]

        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.ctx.eq(self.i.ctx)
        return m


class FPMulStage0(FPState):
    """ First stage of mul.  
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "multiply_0")
        self.mod = FPMulStage0Mod(width)
        self.o = self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        # NOTE: these could be done as combinatorial (merge mul0+mul1)
        m.d.sync += self.o.eq(self.mod.o)

    def action(self, m):
        m.next = "multiply_1"

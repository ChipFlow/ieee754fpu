# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPNumBase, FPNumBaseRecord
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPBaseData


class FPAddStage0Data:

    def __init__(self, width, pspec):
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.tot = Signal(self.z.m_width + 4, reset_less=True)
        self.ctx = FPBaseData(width, pspec)
        self.muxid = self.ctx.muxid

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.tot.eq(i.tot), self.ctx.eq(i.ctx)]


class FPAddStage0Mod(Elaboratable):

    def __init__(self, width, pspec):
        self.width = width
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.pspec, True)

    def ospec(self):
        return FPAddStage0Data(self.width, self.pspec)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.add0 = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        #m.submodules.add0_in_a = self.i.a
        #m.submodules.add0_in_b = self.i.b
        #m.submodules.add0_out_z = self.o.z

        # store intermediate tests (and zero-extended mantissas)
        seq = Signal(reset_less=True)
        mge = Signal(reset_less=True)
        am0 = Signal(len(self.i.a.m)+1, reset_less=True)
        bm0 = Signal(len(self.i.b.m)+1, reset_less=True)
        m.d.comb += [seq.eq(self.i.a.s == self.i.b.s),
                     mge.eq(self.i.a.m >= self.i.b.m),
                     am0.eq(Cat(self.i.a.m, 0)),
                     bm0.eq(Cat(self.i.b.m, 0))
                    ]
        # same-sign (both negative or both positive) add mantissas
        with m.If(~self.i.out_do_z):
            m.d.comb += self.o.z.e.eq(self.i.a.e)
            with m.If(seq):
                m.d.comb += [
                    self.o.tot.eq(am0 + bm0),
                    self.o.z.s.eq(self.i.a.s)
                ]
            # a mantissa greater than b, use a
            with m.Elif(mge):
                m.d.comb += [
                    self.o.tot.eq(am0 - bm0),
                    self.o.z.s.eq(self.i.a.s)
                ]
            # b mantissa greater than a, use b
            with m.Else():
                m.d.comb += [
                    self.o.tot.eq(bm0 - am0),
                    self.o.z.s.eq(self.i.b.s)
            ]

        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.ctx.eq(self.i.ctx)
        return m


class FPAddStage0(FPState):
    """ First stage of add.  covers same-sign (add) and subtract
        special-casing when mantissas are greater or equal, to
        give greatest accuracy.
    """

    def __init__(self, width, pspec):
        FPState.__init__(self, "add_0")
        self.mod = FPAddStage0Mod(width)
        self.o = self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        # NOTE: these could be done as combinatorial (merge add0+add1)
        m.d.sync += self.o.eq(self.mod.o)

    def action(self, m):
        m.next = "add_1"

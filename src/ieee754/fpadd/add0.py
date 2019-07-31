"""IEEE754 Floating Point Adder Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Signal, Cat
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase

from ieee754.fpcommon.fpbase import FPNumBase, FPNumBaseRecord
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext


class FPAddStage0Data:

    def __init__(self, pspec):
        width = pspec.width
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.tot = Signal(self.z.m_width + 4, reset_less=True) # 4 extra bits
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.tot.eq(i.tot), self.ctx.eq(i.ctx)]


class FPAddStage0Mod(PipeModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "add0")

    def ispec(self):
        return FPSCData(self.pspec, True)

    def ospec(self):
        return FPAddStage0Data(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # store intermediate tests (and zero-extended mantissas)
        seq = Signal(reset_less=True)
        mge = Signal(reset_less=True)
        am0 = Signal(len(self.i.a.m)+1, reset_less=True)
        bm0 = Signal(len(self.i.b.m)+1, reset_less=True)
        comb += [seq.eq(self.i.a.s == self.i.b.s),
                     mge.eq(self.i.a.m >= self.i.b.m),
                     am0.eq(Cat(self.i.a.m, 0)),
                     bm0.eq(Cat(self.i.b.m, 0))
                    ]

        # same-sign (both negative or both positive) add mantissas
        with m.If(~self.i.out_do_z):
            comb += self.o.z.e.eq(self.i.a.e)
            with m.If(seq):
                comb += [
                    self.o.tot.eq(am0 + bm0),
                    self.o.z.s.eq(self.i.a.s)
                ]
            # a mantissa greater than b, use a
            with m.Elif(mge):
                comb += [
                    self.o.tot.eq(am0 - bm0),
                    self.o.z.s.eq(self.i.a.s)
                ]
            # b mantissa greater than a, use b
            with m.Else():
                comb += [
                    self.o.tot.eq(bm0 - am0),
                    self.o.z.s.eq(self.i.b.s)
            ]

        # pass-through context
        comb += self.o.oz.eq(self.i.oz)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

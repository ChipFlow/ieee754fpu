"""IEEE754 Floating Point Multiplier Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Signal, Cat, Elaboratable
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext


class FPMulStage0Data:

    def __init__(self, pspec):
        width = pspec.width
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        mw = (self.z.m_width)*2 - 1 + 3 # sticky/round/guard bits + (2*mant) - 1
        self.product = Signal(mw, reset_less=True)
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.product.eq(i.product), self.ctx.eq(i.ctx)]


class FPMulStage0Mod(PipeModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "mul0")

    def ispec(self):
        return FPSCData(self.pspec, False)

    def ospec(self):
        return FPMulStage0Data(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # store intermediate tests (and zero-extended mantissas)
        am0 = Signal(len(self.i.a.m)+1, reset_less=True)
        bm0 = Signal(len(self.i.b.m)+1, reset_less=True)
        comb += [
                     am0.eq(Cat(self.i.a.m, 0)),
                     bm0.eq(Cat(self.i.b.m, 0))
                    ]
        # same-sign (both negative or both positive) mul mantissas
        with m.If(~self.i.out_do_z):
            comb += [self.o.z.e.eq(self.i.a.e + self.i.b.e + 1),
                         self.o.product.eq(am0 * bm0 * 4),
                         self.o.z.s.eq(self.i.a.s ^ self.i.b.s)
                ]

        comb += self.o.oz.eq(self.i.oz)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

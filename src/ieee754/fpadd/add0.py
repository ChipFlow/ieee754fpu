"""IEEE754 Floating Point Adder Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Signal, Cat, Mux
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase

from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpadd.datastruct import FPAddStage0Data


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
        a = self.i.a
        b = self.i.b
        assert len(a.m) == len(b.m) # op lengths must be equal

        # store intermediate tests (and zero-extended mantissas)
        seq = Signal(reset_less=True)
        mge = Signal(reset_less=True)
        sm = Signal(reset_less=True)
        op1 = Signal(len(a.m)+1, reset_less=True)
        op2 = Signal(len(b.m)+1, reset_less=True)

        # logic is as follows:
        # * same-sign (both negative or both positive) add mantissas
        # * opposite sign, subtract b mantissa from a
        # * a mantissa greater than b, use a
        # * b mantissa greater than a, use b
        comb += [seq.eq(a.s == b.s),
                 mge.eq(a.m >= b.m),
                 sm.eq(seq | mge),
                 op1.eq(Cat(Mux(sm, a.m, b.m), 0)), # swap a and b
                 op2.eq(Cat(Mux(sm, b.m, a.m), 0)), # swap b and a
                ]

        # perform add into output z (s/m/e)
        comb += self.o.z.e.eq(a.e)                            # exponent same
        comb += self.o.z.s.eq(Mux(sm, a.s, b.s))              # sign swap
        comb += self.o.tot.eq(Mux(seq, op1 + op2, op1 - op2)) # mantissa +/-

        # pass-through context
        comb += self.o.oz.eq(self.i.oz)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

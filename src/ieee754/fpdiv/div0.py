"""IEEE754 Floating Point Divider

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2019 Jacob Lifshay

Relevant bugreports:
* http://bugs.libre-riscv.org/show_bug.cgi?id=99
* http://bugs.libre-riscv.org/show_bug.cgi?id=43
* http://bugs.libre-riscv.org/show_bug.cgi?id=44

"""

from nmigen import Module, Signal, Cat, Elaboratable, Const, Mux
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.div_rem_sqrt_rsqrt.div_pipe import DivPipeInputData
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation as DPCOp


class FPDivStage0Mod(PipeModBase):
    """ DIV/SQRT/RSQRT "preparation" module.

        adjusts mantissa and exponent (sqrt/rsqrt exponent must be even),
        puts exponent (and sign) into data structures for passing through to
        the end, and puts the (adjusted) mantissa into the processing engine.

        no *actual* processing occurs here: it is *purely* preparation work.
    """

    def __init__(self, pspec):
        super().__init__(pspec, "div0")

    def ispec(self):
        return FPSCData(self.pspec, False)

    def ospec(self):
        return DivPipeInputData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # mantissas start in the range [1.0, 2.0)

        # intermediary temp signals
        is_div = Signal(reset_less=True)
        need_exp_adj = Signal(reset_less=True)

        # "adjusted" - ``self.i.a.rmw`` fractional bits and 2 integer bits
        adj_a_mw = self.i.a.rmw
        adj_a_m = Signal(self.i.a.rmw + 2, reset_less=True)
        adj_a_e = Signal((len(self.i.a.e), True), reset_less=True)

        # adjust (shift) the exponent so that it is even, but only for [r]sqrt
        comb += [is_div.eq(self.i.ctx.op == int(DPCOp.UDivRem)),
                 need_exp_adj.eq(~is_div & self.i.a.e[0]), # even? !div? adjust
                 adj_a_m.eq(self.i.a.m << need_exp_adj),
                 adj_a_e.eq(self.i.a.e - need_exp_adj)]

        # adj_a_m now in the range [1.0, 4.0) for sqrt/rsqrt
        # and [1.0, 2.0) for div

        fw = self.pspec.core_config.fract_width
        divr_rad = Signal(len(self.o.divisor_radicand), reset_less=True)

        # real mantissa fractional widths
        a_mw = self.i.a.rmw
        b_mw = self.i.b.rmw

        comb += [self.o.dividend.eq(self.i.a.m << (fw*2 - a_mw)),
                 divr_rad.eq(Mux(is_div, self.i.b.m << (fw - b_mw),
                                         adj_a_m << (fw - adj_a_mw))),
                 self.o.divisor_radicand.eq(divr_rad),
        ]

        with m.If(~self.i.out_do_z):
            # DIV
            with m.If(self.i.ctx.op == int(DPCOp.UDivRem)):
                comb += [self.o.z.e.eq(self.i.a.e - self.i.b.e),
                         self.o.z.s.eq(self.i.a.s ^ self.i.b.s),
                         self.o.operation.eq(int(DPCOp.UDivRem))
                        ]

            # SQRT
            with m.Elif(self.i.ctx.op == int(DPCOp.SqrtRem)):
                comb += [self.o.z.e.eq(adj_a_e >> 1),
                         self.o.z.s.eq(self.i.a.s),
                         self.o.operation.eq(int(DPCOp.SqrtRem))
                        ]

            # RSQRT
            with m.Elif(self.i.ctx.op == int(DPCOp.RSqrtRem)):
                comb += [self.o.z.e.eq(-(adj_a_e >> 1)),
                         self.o.z.s.eq(self.i.a.s),
                         self.o.operation.eq(int(DPCOp.RSqrtRem))
                        ]

        # these are required and must not be touched
        comb += self.o.oz.eq(self.i.oz)
        comb += self.o.out_do_z.eq(self.i.out_do_z)
        comb += self.o.ctx.eq(self.i.ctx)

        return m



"""IEEE754 Floating Point Divider

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99
"""

from nmigen import Module, Signal, Cat, Elaboratable, Const, Mux
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import (FPNumBaseRecord, Overflow)
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.div_rem_sqrt_rsqrt.div_pipe import DivPipeInputData
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation as DPCOp


class FPDivStage0Mod(Elaboratable):

    def __init__(self, pspec):
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPSCData(self.pspec, False)

    def ospec(self):
        return DivPipeInputData(self.pspec)

    def process(self, i):
        return self.o

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.div0 = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # XXX TODO, actual DIV code here.  this class would be
        # "step one" which takes the pre-normalised data (see ispec) and
        # *begins* the processing phase (enters the massive DIV
        # pipeline chain) - see ospec.

        # INPUT SPEC: FPSCData
        # OUTPUT SPEC: DivPipeInputData

        # NOTE: this stage does *NOT* do *ACTUAL* DIV processing,
        # it is PURELY the *ENTRY* point into the chain, performing
        # "preparation" work.

        # mantissas start in the range [1.0, 2.0)

        is_div = Signal(reset_less=True)
        need_exp_adj = Signal(reset_less=True)

        # ``self.i.a.rmw`` fractional bits and 2 integer bits
        adj_a_m_fract_width = self.i.a.rmw
        adj_a_m = Signal(self.i.a.rmw + 2, reset_less=True)

        adj_a_e = Signal((len(self.i.a.e), True), reset_less=True)

        comb += [is_div.eq(self.i.ctx.op == int(DPCOp.UDivRem)),
                 need_exp_adj.eq(~is_div & self.i.a.e[0]),
                 adj_a_m.eq(self.i.a.m << need_exp_adj),
                 adj_a_e.eq(self.i.a.e - need_exp_adj)]

        # adj_a_m now in the range [1.0, 4.0) for sqrt/rsqrt
        # and [1.0, 2.0) for div

        dividend_fract_width = self.pspec.core_config.fract_width * 2
        dividend = Signal(len(self.o.dividend), reset_less=True)

        divr_rad_fract_width = self.pspec.core_config.fract_width
        divr_rad = Signal(len(self.o.divisor_radicand), reset_less=True)

        a_m_fract_width = self.i.a.rmw
        b_m_fract_width = self.i.b.rmw

        comb += [
            dividend.eq(self.i.a.m << (
                dividend_fract_width - a_m_fract_width)),
            divr_rad.eq(Mux(is_div,
                            self.i.b.m << (
                                divr_rad_fract_width - b_m_fract_width),
                            adj_a_m << (
                                divr_rad_fract_width - adj_a_m_fract_width))),
        ]

        comb += [self.o.dividend.eq(dividend),
                 self.o.divisor_radicand.eq(divr_rad),
        ]

        # set default since it's not always set; non-zero value for debugging
        comb += self.o.operation.eq(1)

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


class FPDivStage0(FPState):
    """ First stage of div.
    """

    def __init__(self, pspec):
        FPState.__init__(self, "divider_0")
        self.mod = FPDivStage0Mod(pspec)
        self.o = self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        # NOTE: these could be done as combinatorial (merge div0+div1)
        m.d.sync += self.o.eq(self.mod.o)

    def action(self, m):
        m.next = "divider_1"

"""IEEE754 Floating Point Divider

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99
"""

from nmigen import Module, Signal, Cat, Elaboratable, Const
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import (FPNumBaseRecord, Overflow)
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.div_rem_sqrt_rsqrt.div_pipe import DivPipeInputData


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

        # XXX TODO, actual DIV code here.  this class would be
        # "step one" which takes the pre-normalised data (see ispec) and
        # *begins* the processing phase (enters the massive DIV
        # pipeline chain) - see ospec.

        # INPUT SPEC: FPSCData
        # OUTPUT SPEC: DivPipeInputData

        # NOTE: this stage does *NOT* do *ACTUAL* DIV processing,
        # it is PURELY the *ENTRY* point into the chain, performing
        # "preparation" work.

        with m.If(~self.i.out_do_z):
            # do conversion here, of both self.i.a and self.i.b,
            # into DivPipeInputData dividend and divisor.

            # XXX *sigh* magic constants...
            if self.pspec.width == 16:
                if self.pspec.log2_radix == 1:
                    extra = 2
                elif self.pspec.log2_radix == 3:
                    extra = 2
                else:
                    extra = 3
            elif self.pspec.width == 32:
                if self.pspec.log2_radix == 1:
                    extra = 3
                else:
                    extra = 4
            elif self.pspec.width == 64:
                if self.pspec.log2_radix == 1:
                    extra = 2
                elif self.pspec.log2_radix == 3:
                    extra = 2
                else:
                    extra = 3

            # the mantissas, having been de-normalised (and containing
            # a "1" in the MSB) represent numbers in the range 0.5 to
            # 0.9999999-recurring.  the min and max range of the
            # result is therefore 0.4999999 (0.5/0.99999) and 1.9999998
            # (0.99999/0.5).

            # DIV
            with m.If(self.i.ctx.op == 0):
                am0 = Signal(len(self.i.a.m)+3, reset_less=True)
                bm0 = Signal(len(self.i.b.m)+3, reset_less=True)
                m.d.comb += [
                             am0.eq(Cat(self.i.a.m, 0)),
                             bm0.eq(Cat(self.i.b.m, 0)),
                            ]

                # zero-extend the mantissas (room for sticky/round/guard)
                # plus the extra MSB.
                m.d.comb += [self.o.z.e.eq(self.i.a.e - self.i.b.e + 1),
                             self.o.z.s.eq(self.i.a.s ^ self.i.b.s),
                             self.o.dividend[len(self.i.a.m)+extra:].eq(am0),
                             self.o.divisor_radicand.eq(bm0),
                             self.o.operation.eq(Const(0)) # XXX DIV operation
                    ]

            # SQRT
            with m.Elif(self.i.ctx.op == 1):
                am0 = Signal(len(self.i.a.m)+3, reset_less=True)
                with m.If(self.i.a.e[0]):
                    m.d.comb += am0.eq(Cat(self.i.a.m, 0)<<(extra-2))
                    m.d.comb += self.o.z.e.eq(((self.i.a.e+1) >> 1)+1)
                with m.Else():
                    m.d.comb += am0.eq(Cat(0, self.i.a.m)<<(extra-2))
                    m.d.comb += self.o.z.e.eq((self.i.a.e >> 1)+1)

                m.d.comb += [self.o.z.s.eq(self.i.a.s),
                             self.o.divisor_radicand.eq(am0),
                             self.o.operation.eq(Const(1)) # XXX SQRT operation
                    ]

        # these are required and must not be touched
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

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

"""IEEE754 Floating Point Divider

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99
"""

from nmigen import Module, Signal, Cat, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import (FPNumBaseRecord, Overflow)
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.div_rem_sqrt_rsqrt.div_pipe import DivPipeInputData


# TODO: delete (replace by DivPipeCoreInputData)
class FPDivStage0Data:

    def __init__(self, pspec):
        self.z = FPNumBaseRecord(pspec.width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(pspec.width, reset_less=True)

        self.ctx = FPPipeContext(pspec.width, pspec) # context: muxid, operator etc.
        self.muxid = self.ctx.muxid             # annoying. complicated.

        # TODO: here is where Q and R would be put, and passed
        # down to Stage1 processing.

        mw = (self.z.m_width)*2 - 1 + 3 # sticky/round/guard bits + (2*mant) - 1
        self.product = Signal(mw, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.product.eq(i.product), self.ctx.eq(i.ctx)]


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
        # OUTPUT SPEC: DivPipeCoreInputData

        # NOTE: this stage does *NOT* do *ACTUAL* DIV processing,
        # it is PURELY the *ENTRY* point into the chain, performing
        # "preparation" work.

        with m.If(~self.i.out_do_z):
            # do conversion here, of both self.i.a and self.i.b,
            # into DivPipeCoreInputData dividend and divisor.

            # the mantissas, having been de-normalised (and containing
            # a "1" in the MSB) represent numbers in the range 0.5 to
            # 0.9999999-recurring.  the min and max range of the
            # result is therefore 0.4999999 (0.5/0.99999) and 1.9999998
            # (0.99999/0.5).

            # zero-extend the mantissas (room for sticky/guard)
            # plus the extra MSB.  See DivPipeBaseStage.get_core_config
            am0 = Signal(len(self.i.a.m)+3, reset_less=True)
            bm0 = Signal(len(self.i.b.m)+3, reset_less=True)
            m.d.comb += [
                         am0.eq(Cat(0, 0, self.i.a.m, 0)),
                         bm0.eq(Cat(0, 0, self.i.b.m, 0))
                        ]

            m.d.comb += [self.o.z.e.eq(self.i.a.e - self.i.b.e + 1),
                         self.o.z.s.eq(self.i.a.s ^ self.i.b.s),
                         self.o.dividend.eq(am0), # TODO: check
                         self.o.divisor_radicand.eq(bm0), # TODO: check
                         self.o.operation.eq(Const(0)) # TODO check: DIV
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

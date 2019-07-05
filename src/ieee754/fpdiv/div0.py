"""IEEE754 Floating Point Divider 

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99
"""

from nmigen import Module, Signal, Cat, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import (FPNumBaseRecord, Overflow)
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.getop import FPPipeContext


# TODO: delete (replace by DivPipeCoreInputData)
class FPDivStage0Data:

    def __init__(self, width, pspec):
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)

        self.ctx = FPPipeContext(width, pspec) # context: muxid, operator etc.
        self.muxid = self.ctx.muxid             # annoying. complicated.

        # TODO: here is where Q and R would be put, and passed
        # down to Stage1 processing.

        mw = (self.z.m_width)*2 - 1 + 3 # sticky/round/guard bits + (2*mant) - 1
        self.product = Signal(mw, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.product.eq(i.product), self.ctx.eq(i.ctx)]


class FPDivStage0Mod(Elaboratable):

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.id_wid, False)

    def ospec(self):
        # XXX TODO: replace with DivPipeCoreInputData, here
        return FPDivStage0Data(self.width, self.id_wid)

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

        # delete this
        # store intermediate tests (and zero-extended mantissas)
        am0 = Signal(len(self.i.a.m)+1, reset_less=True)
        bm0 = Signal(len(self.i.b.m)+1, reset_less=True)
        m.d.comb += [
                     am0.eq(Cat(self.i.a.m, 0)),
                     bm0.eq(Cat(self.i.b.m, 0))
                    ]

        with m.If(~self.i.out_do_z):
            # do conversion here, of both self.i.a and self.i.b,
            # into DivPipeCoreInputData dividend and divisor.

            m.d.comb += [self.o.z.e.eq(self.i.a.e + self.i.b.e + 1),
                         # TODO: no, not product, first stage Q and R etc. etc.
                         # go here.
                         self.o.product.eq(am0 * bm0 * 4),
                         self.o.z.s.eq(self.i.a.s ^ self.i.b.s)
                ]

        # these are required and must not be touched
        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPDivStage0(FPState):
    """ First stage of div.  
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "divider_0")
        self.mod = FPDivStage0Mod(width)
        self.o = self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

        # NOTE: these could be done as combinatorial (merge div0+div1)
        m.d.sync += self.o.eq(self.mod.o)

    def action(self, m):
        m.next = "divider_1"

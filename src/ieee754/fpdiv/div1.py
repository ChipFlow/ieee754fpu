"""IEEE754 Floating Point Divider 

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99
"""

from nmigen import Module, Signal, Cat, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from .div0 import FPDivStage0Data


class FPDivStage1Mod(Elaboratable):

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPDivStage0Data(self.width, self.id_wid)

    def ospec(self):
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
        # "step two" and is the main "chain".  tons of these needed.
        # here is where Q and R are used, TODO: those are in FPDivStage0Data.

        # store intermediate tests (and zero-extended mantissas)
        am0 = Signal(len(self.i.a.m)+1, reset_less=True)
        bm0 = Signal(len(self.i.b.m)+1, reset_less=True)
        m.d.comb += [
                     am0.eq(Cat(self.i.a.m, 0)),
                     bm0.eq(Cat(self.i.b.m, 0))
                    ]
        # same-sign (both negative or both positive) div mantissas
        with m.If(~self.i.out_do_z):
            m.d.comb += [self.o.z.e.eq(self.i.a.e + self.i.b.e + 1),
                         # TODO: no, not product, first stage Q and R etc. etc.
                         # go here.
                         self.o.product.eq(am0 * bm0 * 4),
                         self.o.z.s.eq(self.i.a.s ^ self.i.b.s)
                ]

        m.d.comb += self.o.oz.eq(self.i.oz)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.mid.eq(self.i.mid)
        return m


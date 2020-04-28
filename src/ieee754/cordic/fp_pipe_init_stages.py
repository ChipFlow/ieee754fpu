from nmigen import Module, Signal, Cat, Const, Mux
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.denorm import FPSCData


class FPCordicInitStage(PipeModBase):
    def __init__(self, pspec):
        super().__init__(pspec, "specialcases")

    def ispec(self):
        return FPBaseData(self.pspec)

    def ospec(self):
        return FPSCData(self.pspec, False)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # decode a/b
        width = self.pspec.width
        a1 = FPNumBaseRecord(width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        comb += [a1.v.eq(self.i.a),
                 self.o.a.eq(a1)
        ]

        #  pass through context
        comb += self.o.ctx.eq(self.i.ctx)

        return m

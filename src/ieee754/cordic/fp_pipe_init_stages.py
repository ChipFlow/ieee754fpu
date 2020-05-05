from nmigen import (Module, Signal, Cat, Const, Mux, Repl, signed,
                    unsigned)
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.denorm import FPSCData
from ieee754.cordic.fp_pipe_data import CordicInitialData


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


class FPCordicConvertFixed(PipeModBase):
    def __init__(self, pspec):
        super().__init__(pspec, "tofixed")

    def ispec(self):
        return FPSCData(self.pspec, False)

    def ospec(self):
        return CordicInitialData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        shifter = Signal(self.i.a.e.width)
        comb += shifter.eq(-self.i.a.e)

        z_intermed = Signal(unsigned(self.o.z0.width))
        z_shifted = Signal(signed(self.o.z0.width))
        comb += z_intermed.eq(Cat(Repl(0, self.pspec.fracbits -
                                       self.i.a.rmw),
                                  self.i.a.m))
        comb += z_shifted.eq(z_intermed >> shifter)
        comb += self.o.z0.eq(Mux(self.i.a.s,
                                 ~z_shifted + 1,
                                 z_shifted))

        comb += self.o.ctx.eq(self.i.ctx)
        return m

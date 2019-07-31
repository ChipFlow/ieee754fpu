"""IEEE754 Floating Point Adder Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module, Signal

from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.getop import FPPipeContext


class FPAddStage0Data:

    def __init__(self, pspec):
        width = pspec.width
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.tot = Signal(self.z.m_width + 4, reset_less=True) # 4 extra bits
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.tot.eq(i.tot), self.ctx.eq(i.ctx)]

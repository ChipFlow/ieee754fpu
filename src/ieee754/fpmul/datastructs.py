"""IEEE754 Floating Point Multiplier Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Signal

from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.getop import FPPipeContext


class FPMulStage0Data:

    def __init__(self, pspec):
        width = pspec.width
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        mw = (self.z.m_width)*2 - 1 + 3 # sticky/round/guard bits + (2*mant) - 1
        self.product = Signal(mw, reset_less=True)
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.product.eq(i.product), self.ctx.eq(i.ctx)]


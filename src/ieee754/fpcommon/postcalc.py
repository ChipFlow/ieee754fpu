# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Signal
from ieee754.fpcommon.fpbase import Overflow, FPNumBaseRecord
from ieee754.fpcommon.getop import FPPipeContext

class FPAddStage1Data:

    def __init__(self, width, pspec):
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.of = Overflow()
        self.ctx = FPPipeContext(width, pspec)
        self.muxid = self.ctx.muxid

    def __iter__(self):
        yield from self.z
        yield self.out_do_z
        yield self.oz
        yield from self.of
        yield from self.ctx

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.of.eq(i.of), self.ctx.eq(i.ctx)]

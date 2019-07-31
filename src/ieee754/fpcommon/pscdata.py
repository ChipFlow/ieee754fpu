"""IEEE754 Floating Point Library

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Signal
from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.getop import FPPipeContext


class FPSCData:

    def __init__(self, pspec, m_extra):
        width = pspec.width
        # NOTE: difference between z and oz is that oz is created by
        # special-cases module(s) and will propagate, along with its
        # "bypass" signal out_do_z, through the pipeline, *disabling*
        # all processing of all subsequent stages.
        self.a = FPNumBaseRecord(width, m_extra, name="a")   # operand a
        self.b = FPNumBaseRecord(width, m_extra, name="b")   # operand b
        self.z = FPNumBaseRecord(width, False, name="z")     # denormed result
        self.oz = Signal(width, reset_less=True)   # "finished" (bypass) result
        self.out_do_z = Signal(reset_less=True)    # "bypass" enabled
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid

    def __iter__(self):
        yield from self.a
        yield from self.b
        yield from self.z
        yield self.oz
        yield self.out_do_z
        yield from self.ctx

    def eq(self, i):
        ret = [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
               self.a.eq(i.a), self.b.eq(i.b), self.ctx.eq(i.ctx)]
        return ret

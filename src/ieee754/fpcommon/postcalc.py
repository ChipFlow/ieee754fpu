# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Signal
from ieee754.fpcommon.fpbase import Overflow, FPNumBaseRecord
from ieee754.fpcommon.getop import FPBaseData

class FPAddStage1Data(FPBaseData):

    def __init__(self, width, id_wid, op_wid=None):
        FPBaseData.__init__(self, 0, width, id_wid, op_wid)
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.of = Overflow()

    def __iter__(self):
        yield from self.z
        yield self.out_do_z
        yield self.oz
        yield from self.of
        yield from FPBaseData.__iter__(self)

    def eq(self, i):
        ret = [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
              self.of.eq(i.of),] + FPBaseData.eq(self, i)

        return ret

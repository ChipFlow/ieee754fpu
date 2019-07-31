# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Signal
from ieee754.fpcommon.getop import FPPipeContext


class FPPackData:

    def __init__(self, pspec):
        width = pspec.width
        self.z = Signal(width, reset_less=True)    # result
        self.ctx = FPPipeContext(pspec)

        # this is complicated: it's a workaround, due to the
        # array-indexing not working properly in nmigen.
        # self.ports() is used to access the ArrayProxy objects by name,
        # however it doesn't work recursively.  the workaround:
        # drop the sub-objects into *this* scope and they can be
        # accessed / set.  it's horrible.
        self.muxid = self.ctx.muxid
        self.op = self.ctx.op

    def eq(self, i):
        return [self.z.eq(i.z), self.ctx.eq(i.ctx)]

    def __iter__(self):
        yield self.z
        yield from self.ctx

    def ports(self):
        return list(self)

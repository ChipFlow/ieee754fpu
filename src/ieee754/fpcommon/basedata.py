# IEEE Floating Point Adder (Single Precision)
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

from nmigen import Signal
from ieee754.fpcommon.getop import FPPipeContext


class FPBaseData:

    def __init__(self, pspec):
        width = pspec.width
        n_ops = pspec.n_ops
        self.ctx = FPPipeContext(pspec)
        ops = []
        for i in range(n_ops):
            name = chr(ord("a")+i)
            operand = Signal(width, name=name)
            setattr(self, name, operand)
            ops.append(operand)
        self.muxid = self.ctx.muxid # make muxid available here: complicated
        self.ops = ops

    def eq(self, i):
        ret = []
        for op1, op2 in zip(self.ops, i.ops):
            ret.append(op1.eq(op2))
        ret.append(self.ctx.eq(i.ctx))
        return ret

    def __iter__(self):
        if self.ops:
            yield from self.ops
        yield from self.ctx

    def ports(self):
        return list(self)



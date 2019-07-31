# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal
from nmigen.cli import main, verilog

from ieee754.fpcommon.modbase import FPModBase
from ieee754.fpcommon.fpbase import FPNumBaseRecord, FPNumBase
from ieee754.fpcommon.roundz import FPRoundData
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


class FPPackMod(FPModBase):

    def __init__(self, pspec):
        super().__init__(pspec, "pack")

    def ispec(self):
        return FPRoundData(self.pspec)

    def ospec(self):
        return FPPackData(self.pspec)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        z = FPNumBaseRecord(self.pspec.width, False, name="z")
        m.submodules.pack_in_z = in_z = FPNumBase(self.i.z)

        with m.If(~self.i.out_do_z):
            with m.If(in_z.is_overflowed):
                comb += z.inf(self.i.z.s)
            with m.Else():
                comb += z.create(self.i.z.s, self.i.z.e, self.i.z.m)
        with m.Else():
            comb += z.v.eq(self.i.oz)

        comb += self.o.ctx.eq(self.i.ctx)
        comb += self.o.z.eq(z.v)

        return m

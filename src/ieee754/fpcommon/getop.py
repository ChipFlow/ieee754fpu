# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Elaboratable
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import FPOpIn, FPBase, FPNumBase
from nmutil.singlepipe import PrevControl

from nmutil import nmoperator


class FPGetOpMod(Elaboratable):
    def __init__(self, width):
        self.in_op = FPOpIn(width)
        self.in_op.data_i = Signal(width)
        self.out_op = Signal(width)
        self.out_decode = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.out_decode.eq((self.in_op.ready_o) & \
                                       (self.in_op.valid_i_test))
        m.submodules.get_op_in = self.in_op
        with m.If(self.out_decode):
            m.d.comb += [
                self.out_op.eq(self.in_op.v),
            ]
        return m


class FPNumBase2Ops:

    def __init__(self, width, id_wid, m_extra=True):
        self.a = FPNumBase(width, m_extra)
        self.b = FPNumBase(width, m_extra)
        self.muxid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.a.eq(i.a), self.b.eq(i.b), self.muxid.eq(i.muxid)]

    def ports(self):
        return [self.a, self.b, self.muxid]


class FPPipeContext:

    def __init__(self, pspec):
        """ creates a pipeline context.  currently: operator (op) and muxid

            opkls (within pspec) - the class to create that will be the
                                   "operator". instance must have an "eq"
                                   function.
        """
        self.id_wid = pspec.id_wid
        self.op_wid = pspec.op_wid
        self.muxid = Signal(self.id_wid, reset_less=True)   # RS multiplex ID
        opkls = pspec.opkls
        if opkls is None:
            self.op = Signal(self.op_wid, reset_less=True)
        else:
            self.op = opkls(pspec)

    def eq(self, i):
        ret = [self.muxid.eq(i.muxid)]
        ret.append(self.op.eq(i.op))
        return ret

    def __iter__(self):
        yield self.muxid
        yield self.op

    def ports(self):
        return list(self)


class FPGet2OpMod(PrevControl):
    def __init__(self, width, id_wid, op_wid=None):
        PrevControl.__init__(self)
        self.width = width
        self.id_wid = id_wid
        self.data_i = self.ispec()
        self.i = self.data_i
        self.o = self.ospec()

    def ispec(self):
        return FPBaseData(self.width, self.id_wid, self.op_wid)

    def ospec(self):
        return FPBaseData(self.width, self.id_wid, self.op_wid)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = PrevControl.elaborate(self, platform)
        with m.If(self.trigger):
            m.d.comb += [
                self.o.eq(self.data_i),
            ]
        return m



# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux, Array, Const, Elaboratable
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import FPNumIn, FPNumOut, FPOpIn, Overflow, FPBase, FPNumBase
from ieee754.fpcommon.fpbase import MultiShiftRMerge, Trigger
from nmutil.singlepipe import (ControlBase, StageChain, SimpleHandshake,
                        PassThroughStage, PrevControl)
from nmutil.multipipe import CombMuxOutPipe
from nmutil.multipipe import PriorityCombMuxInPipe

from ieee754.fpcommon.fpbase import FPState
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
        #m.submodules.get_op_out = self.out_op
        with m.If(self.out_decode):
            m.d.comb += [
                self.out_op.eq(self.in_op.v),
            ]
        return m


class FPGetOp(FPState):
    """ gets operand
    """

    def __init__(self, in_state, out_state, in_op, width):
        FPState.__init__(self, in_state)
        self.out_state = out_state
        self.mod = FPGetOpMod(width)
        self.in_op = in_op
        self.out_op = Signal(width)
        self.out_decode = Signal(reset_less=True)

    def setup(self, m, in_op):
        """ links module to inputs and outputs
        """
        setattr(m.submodules, self.state_from, self.mod)
        m.d.comb += nmoperator.eq(self.mod.in_op, in_op)
        m.d.comb += self.out_decode.eq(self.mod.out_decode)

    def action(self, m):
        with m.If(self.out_decode):
            m.next = self.out_state
            m.d.sync += [
                self.in_op.ready_o.eq(0),
                self.out_op.eq(self.mod.out_op)
            ]
        with m.Else():
            m.d.sync += self.in_op.ready_o.eq(1)


class FPNumBase2Ops:

    def __init__(self, width, id_wid, m_extra=True):
        self.a = FPNumBase(width, m_extra)
        self.b = FPNumBase(width, m_extra)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.a.eq(i.a), self.b.eq(i.b), self.mid.eq(i.mid)]

    def ports(self):
        return [self.a, self.b, self.mid]


class FPADDBaseData:

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.a  = Signal(width)                      # operand a
        self.b  = Signal(width)                      # operand b
        self.mid = Signal(id_wid, reset_less=True)   # RS multiplex ID

    def eq(self, i):
        return [self.a.eq(i.a), self.b.eq(i.b), self.mid.eq(i.mid)]

    def ports(self):
        return [self.a, self.b, self.mid]


class FPGet2OpMod(PrevControl):
    def __init__(self, width, id_wid):
        PrevControl.__init__(self)
        self.width = width
        self.id_wid = id_wid
        self.data_i = self.ispec()
        self.i = self.data_i
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.width, self.id_wid)

    def ospec(self):
        return FPADDBaseData(self.width, self.id_wid)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = PrevControl.elaborate(self, platform)
        with m.If(self.trigger):
            m.d.comb += [
                self.o.eq(self.data_i),
            ]
        return m


class FPGet2Op(FPState):
    """ gets operands
    """

    def __init__(self, in_state, out_state, width, id_wid):
        FPState.__init__(self, in_state)
        self.out_state = out_state
        self.mod = FPGet2OpMod(width, id_wid)
        self.o = self.ospec()
        self.in_stb = Signal(reset_less=True)
        self.out_ack = Signal(reset_less=True)
        self.out_decode = Signal(reset_less=True)

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def trigger_setup(self, m, in_stb, in_ack):
        """ links stb/ack
        """
        m.d.comb += self.mod.valid_i.eq(in_stb)
        m.d.comb += in_ack.eq(self.mod.ready_o)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.get_ops = self.mod
        m.d.comb += self.mod.i.eq(i)
        m.d.comb += self.out_ack.eq(self.mod.ready_o)
        m.d.comb += self.out_decode.eq(self.mod.trigger)

    def process(self, i):
        return self.o

    def action(self, m):
        with m.If(self.out_decode):
            m.next = self.out_state
            m.d.sync += [
                self.mod.ready_o.eq(0),
                self.o.eq(self.mod.o),
            ]
        with m.Else():
            m.d.sync += self.mod.ready_o.eq(1)



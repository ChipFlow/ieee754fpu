# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux, Array, Const
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase, FPNumBase
from fpbase import MultiShiftRMerge, Trigger
from singlepipe import (ControlBase, StageChain, UnbufferedPipeline,
                        PassThroughStage)
from multipipe import CombMuxOutPipe
from multipipe import PriorityCombMuxInPipe

from fpbase import FPState, FPID
from fpcommon.roundz import FPRoundData


class FPPackData:

    def __init__(self, width, id_wid):
        self.z = Signal(width, reset_less=True)
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.mid.eq(i.mid)]

    def ports(self):
        return [self.z, self.mid]


class FPPackMod:

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPRoundData(self.width, self.id_wid)

    def ospec(self):
        return FPPackData(self.width, self.id_wid)

    def process(self, i):
        return self.o

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        m.submodules.pack = self
        m.d.comb += self.i.eq(in_z)

    def elaborate(self, platform):
        m = Module()
        z = FPNumOut(self.width, False)
        m.submodules.pack_in_z = self.i.z
        m.submodules.pack_out_z = z
        m.d.comb += self.o.mid.eq(self.i.mid)
        with m.If(~self.i.out_do_z):
            with m.If(self.i.z.is_overflowed):
                m.d.comb += z.inf(self.i.z.s)
            with m.Else():
                m.d.comb += z.create(self.i.z.s, self.i.z.e, self.i.z.m)
        with m.Else():
            m.d.comb += z.v.eq(self.i.oz)
        m.d.comb += self.o.z.eq(z.v)
        return m


class FPPack(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "pack")
        self.mod = FPPackMod(width)
        self.out_z = self.ospec()

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z)

        m.d.sync += self.out_z.v.eq(self.mod.out_z.v)
        m.d.sync += self.out_z.mid.eq(self.mod.o.mid)

    def action(self, m):
        m.next = "pack_put_z"

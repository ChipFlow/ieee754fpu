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

class FPAddStage1Data:

    def __init__(self, width, id_wid):
        self.z = FPNumBase(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.of = Overflow()
        self.mid = Signal(id_wid, reset_less=True)

    def eq(self, i):
        return [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.of.eq(i.of), self.mid.eq(i.mid)]

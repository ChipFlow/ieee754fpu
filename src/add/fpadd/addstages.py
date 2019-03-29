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
from fpcommon.denorm import FPSCData
from fpcommon.postcalc import FPAddStage1Data
from fpadd.align import FPAddAlignSingleMod
from fpadd.add0 import (FPAddStage0Data, FPAddStage0Mod, FPAddStage0)
from fpadd.add1 import (FPAddStage1Mod, FPAddStage1)


class FPAddAlignSingleAdd(FPState, UnbufferedPipeline):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "align")
        self.width = width
        self.id_wid = id_wid
        UnbufferedPipeline.__init__(self, self) # pipeline is its own stage
        self.a1o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.id_wid)

    def ospec(self):
        return FPAddStage1Data(self.width, self.id_wid) # AddStage1 ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # chain AddAlignSingle, AddStage0 and AddStage1
        mod = FPAddAlignSingleMod(self.width, self.id_wid)
        a0mod = FPAddStage0Mod(self.width, self.id_wid)
        a1mod = FPAddStage1Mod(self.width, self.id_wid)

        chain = StageChain([mod, a0mod, a1mod])
        chain.setup(m, i)

        self.o = a1mod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.a1o.eq(self.process(None))
        m.next = "normalise_1"



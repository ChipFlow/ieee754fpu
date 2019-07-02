# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import (StageChain, SimpleHandshake,
                        PassThroughStage)

from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPAddStage1Data
from .align import FPAddAlignSingleMod
from .add0 import FPAddStage0Mod
from .add1 import FPAddStage1Mod


class FPAddAlignSingleAdd(FPState, SimpleHandshake):

    def __init__(self, width, pspec):
        FPState.__init__(self, "align")
        self.width = width
        self.pspec = pspec
        SimpleHandshake.__init__(self, self) # pipeline is its own stage
        self.a1o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.pspec, True)

    def ospec(self):
        return FPAddStage1Data(self.width, self.pspec) # AddStage1 ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # chain AddAlignSingle, AddStage0 and AddStage1
        mod = FPAddAlignSingleMod(self.width, self.pspec)
        a0mod = FPAddStage0Mod(self.width, self.pspec)
        a1mod = FPAddStage1Mod(self.width, self.pspec)

        chain = StageChain([mod, a0mod, a1mod])
        chain.setup(m, i)

        self.o = a1mod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.a1o.eq(self.process(None))
        m.next = "normalise_1"



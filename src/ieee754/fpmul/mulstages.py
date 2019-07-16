# IEEE Floating Point Multiplier

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import (StageChain, SimpleHandshake)

from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPAddStage1Data
from .mul0 import FPMulStage0Mod
from .mul1 import FPMulStage1Mod


class FPMulStages(FPState, SimpleHandshake):

    def __init__(self, pspec):
        FPState.__init__(self, "mulstages")
        self.pspec = pspec
        SimpleHandshake.__init__(self, self) # pipeline is its own stage
        self.m1o = self.ospec()

    def ispec(self):
        return FPSCData(self.pspec, False)

    def ospec(self):
        return FPAddStage1Data(self.pspec)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # chain MulStage0 and MulStage1
        m0mod = FPMulStage0Mod(self.pspec)
        m1mod = FPMulStage1Mod(self.pspec)

        chain = StageChain([m0mod, m1mod])
        chain.setup(m, i)

        self.o = m1mod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.m1o.eq(self.process(None))
        m.next = "normalise_1"



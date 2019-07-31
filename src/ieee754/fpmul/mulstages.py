# IEEE Floating Point Multiplier

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import StageChain

from ieee754.pipeline import DynamicPipe
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPAddStage1Data
from ieee754.fpmul.mul0 import FPMulStage0Mod
from ieee754.fpmul.mul1 import FPMulStage1Mod


class FPMulStages(DynamicPipe):

    def __init__(self, pspec):
        self.pspec = pspec
        super().__init__(pspec)

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


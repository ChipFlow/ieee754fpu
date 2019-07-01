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

    def __init__(self, width, id_wid, op_wid=None):
        FPState.__init__(self, "align")
        self.width = width
        self.id_wid = id_wid
        self.op_wid = op_wid
        SimpleHandshake.__init__(self, self) # pipeline is its own stage
        self.m1o = self.ospec()

    def ispec(self):
        return FPSCData(self.width, self.id_wid, False, self.op_wid)

    def ospec(self):
        return FPAddStage1Data(self.width, self.id_wid, self.op_wid)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # chain MulStage0 and MulStage1
        m0mod = FPMulStage0Mod(self.width, self.id_wid, self.op_wid)
        m1mod = FPMulStage1Mod(self.width, self.id_wid, self.op_wid)

        chain = StageChain([m0mod, m1mod])
        chain.setup(m, i)

        self.o = m1mod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.m1o.eq(self.process(None))
        m.next = "normalise_1"



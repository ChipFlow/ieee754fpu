# IEEE Floating Point Multiplier

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import StageChain

from nmutil.pipemodbase import PipeModBaseChain
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPPostCalcData
from ieee754.fpmul.mul0 import FPMulStage0Mod
from ieee754.fpmul.mul1 import FPMulStage1Mod


class FPMulStages(PipeModBaseChain):

    def get_chain(self):
        # chain MulStage0 and MulStage1
        m0mod = FPMulStage0Mod(self.pspec)
        m1mod = FPMulStage1Mod(self.pspec)

        return [m0mod, m1mod]


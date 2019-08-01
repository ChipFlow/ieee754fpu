"""IEEE754 Floating Point Multiplier Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2019 Jake Lifshay

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=77

Stack looks like this:

* scnorm    - FPMulSpecialCasesDeNorm
* mulstages - FPMulstages
* normpack  - FPNormToPack

scnorm   - FPDIVSpecialCasesDeNorm ispec FPBaseData
------                             ospec FPSCData

                StageChain: FPMULSpecialCasesMod,
                            FPAddDeNormMod
                            FPAlignModSingle

mulstages - FPMulStages            ispec FPSCData
---------                          ospec FPPostCalcData

                StageChain: FPMulStage0Mod
                            FPMulStage1Mod

normpack  - FPNormToPack           ispec FPPostCalcData
--------                           ospec FPPackData

                StageChain: Norm1ModSingle,
                            RoundMod,
                            CorrectionsMod,
                            PackMod

This is the *current* stack.  FPMulStage0Mod is where the actual
mantissa multiply takes place, which in the case of FP64 is a
single (massive) combinatorial block.  This can be fixed by using
a multi-stage fixed-point multiplier pipeline, which was implemented
in #60: http://bugs.libre-riscv.org/show_bug.cgi?id=60

"""

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.normtopack import FPNormToPack
from .specialcases import FPMulSpecialCasesDeNorm
from .mulstages import FPMulStages
from ieee754.pipeline import PipelineSpec


class FPMULBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.pipe1 = FPMulSpecialCasesDeNorm(pspec)
        self.pipe2 = FPMulStages(pspec)
        self.pipe3 = FPNormToPack(pspec)

        self._eqs = self.connect([self.pipe1, self.pipe2, self.pipe3])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.scnorm = self.pipe1
        m.submodules.mulstages = self.pipe2
        m.submodules.normpack = self.pipe3
        m.d.comb += self._eqs
        return m


class FPMULMuxInOut(ReservationStations):
    """ Reservation-Station version of FPMUL pipeline.

        * fan-in on inputs (an array of FPBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, width, num_rows, op_wid=0):
        self.id_wid = num_bits(num_rows)
        self.op_wid = op_wid
        self.pspec = PipelineSpec(width, self.id_wid, self.op_wid)
        self.alu = FPMULBasePipe(self.pspec)
        ReservationStations.__init__(self, num_rows)

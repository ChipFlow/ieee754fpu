"""IEEE754 Floating Point pipelined Divider

This module simply constructs register-based pipeline(s) out of
appropriate combinatorial blocks: setup, intermediary and final
single-clock pipelines.

"actual" processing is carried out by the DivPipeCalculateStage
combinatorial block: everything else is chaining and pre- and post-
data formatting.

there's no "actual" work done here: it's just a "joining-together" job.
see pipeline.py for an ASCII diagram showing how everything fits together

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99

"""

from nmutil.pipemodbase import PipeModBaseChain
from ieee754.div_rem_sqrt_rsqrt.div_pipe import (DivPipeInterstageData,
                                                 DivPipeSetupStage,
                                                 DivPipeCalculateStage,
                                                 DivPipeFinalStage,
                                                )
from ieee754.fpdiv.div0 import FPDivPreFPAdjust
from ieee754.fpdiv.div2 import FPDivPostToFPFormat


class FPDivStagesSetup(PipeModBaseChain):

    def __init__(self, pspec, n_stages, stage_offs):
        self.n_stages = n_stages # number of combinatorial stages
        self.stage_offs = stage_offs # each CalcStage needs *absolute* idx
        super().__init__(pspec)

    def get_chain(self):
        """ gets module chain

            note: this is a pure *combinatorial* module (StageChain).
            therefore each sub-module must also be combinatorial
        """

        # chain to be returned
        divstages = []

        # Converts from FPSCData into DivPipeInputData
        divstages.append(FPDivPreFPAdjust(self.pspec))

        # does 1 "convert" (actual processing) from DivPipeInputData
        # into "intermediate" output (DivPipeInterstageData)
        divstages.append(DivPipeSetupStage(self.pspec))

        # here is where the intermediary stages are added.
        for count in range(self.n_stages): # number of combinatorial stages
            idx = count + self.stage_offs
            divstages.append(DivPipeCalculateStage(self.pspec, idx))

        return divstages


class FPDivStagesIntermediate(PipeModBaseChain):

    def __init__(self, pspec, n_stages, stage_offs):
        self.n_stages = n_stages # number of combinatorial stages
        self.stage_offs = stage_offs # each CalcStage needs *absolute* idx
        super().__init__(pspec)

    def get_chain(self):
        """ gets module chain

            note: this is a pure *combinatorial* module (StageChain).
            therefore each sub-module must also be combinatorial
        """

        # chain to be returned
        divstages = []

        # here is where the intermediary stages are added.
        for count in range(self.n_stages): # number of combinatorial stages
            idx = count + self.stage_offs
            divstages.append(DivPipeCalculateStage(self.pspec, idx))

        return divstages


class FPDivStagesFinal(PipeModBaseChain):

    def __init__(self, pspec, n_stages, stage_offs):
        self.n_stages = n_stages # number of combinatorial stages
        self.stage_offs = stage_offs # each CalcStage needs *absolute* idx
        super().__init__(pspec)

    def get_chain(self):
        """ gets module chain

            note: this is a pure *combinatorial* module (StageChain).
            therefore each sub-module must also be combinatorial
        """

        # chain to be returned
        divstages = []

        # here is where the last intermediary stages are added.
        for count in range(self.n_stages): # number of combinatorial stages
            idx = count + self.stage_offs
            divstages.append(DivPipeCalculateStage(self.pspec, idx))

        # does the final conversion from intermediary to output data
        divstages.append(DivPipeFinalStage(self.pspec))

        # does conversion from DivPipeOutputData into FPPostCalcData format
        # so that post-normalisation and corrections can take over
        divstages.append(FPDivPostToFPFormat(self.pspec))

        return divstages

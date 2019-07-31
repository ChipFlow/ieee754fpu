"""IEEE754 Floating Point pipelined Divider

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99

"""

from nmutil.pipemodbase import PipeModBaseChain
from ieee754.div_rem_sqrt_rsqrt.div_pipe import (DivPipeInterstageData,
                                                 DivPipeSetupStage,
                                                 DivPipeCalculateStage,
                                                 DivPipeFinalStage,
                                                )
from ieee754.fpdiv.div0 import FPDivStage0Mod
from ieee754.fpdiv.div2 import FPDivStage2Mod


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

        divstages = []

        # Converts from FPSCData into DivPipeInputData
        divstages.append(FPDivStage0Mod(self.pspec))

        # does 1 "convert" (actual processing) from DivPipeInputData
        # into "intermediate" output (DivPipeInterstageData)
        divstages.append(DivPipeSetupStage(self.pspec))

        # here is where the intermediary stages are added.
        # n_stages is adjusted (by pipeline.py), reduced to take
        # into account extra processing that FPDivStage0Mod and DivPipeSetup
        # might add.
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

        divstages = []

        # here is where the intermediary stages are added.
        # n_stages is adjusted (in pipeline.py), reduced to take
        # into account the extra processing that self.begin and self.end
        # will add.
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

        # takes the DIV pipeline/chain data and munges it
        # into the format that the normalisation can accept.

        divstages = []

        # here is where the intermediary stages are added.
        # n_stages is adjusted (in pipeline.py), reduced to take
        # into account the extra processing that self.begin and self.end
        # will add.
        for count in range(self.n_stages): # number of combinatorial stages
            idx = count + self.stage_offs
            divstages.append(DivPipeCalculateStage(self.pspec, idx))

        # does the final conversion from intermediary to output data
        divstages.append(DivPipeFinalStage(self.pspec))

        # does conversion from DivPipeOutputData into
        # FPAddStage1Data format (bad name, TODO, doesn't matter),
        # so that post-normalisation and corrections can take over
        divstages.append(FPDivStage2Mod(self.pspec))

        return divstages

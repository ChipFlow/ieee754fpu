from nmutil.singlepipe import ControlBase
from nmutil.pipemodbase import PipeModBaseChain

from ieee754.fpcommon.denorm import FPAddDeNormMod
from ieee754.cordic.fp_pipe_init_stages import (FPCordicInitStage)


class CordicPipeChain(PipeModBaseChain):
    def __init__(self, pspec, stages):
        self.stages = stages
        super().__init__(pspec)

    def get_chain(self):
        return self.stages


class FPCordicBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.pspec = pspec

        self.denorm = CordicPipeChain(pspec,
                                      [FPCordicInitStage(self.pspec),
                                       FPAddDeNormMod(self.pspec, False)])

        self._eqs = self.connect([self.denorm])

    def chunkify(self, initstage, stages):
        chunks = []

        for i in range(0, len(stages), self.pspec.rounds_per_stage):
            chunks.append(stages[i:i + self.pspec.rounds_per_stage])
        chunks[0].insert(0, initstage)

        return chunks

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.denorm = self.denorm
        m.d.comb += self._eqs
        return m

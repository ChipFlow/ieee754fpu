from nmutil.singlepipe import ControlBase
from nmutil.pipemodbase import PipeModBaseChain

from ieee754.fpcommon.denorm import FPAddDeNormMod
from ieee754.cordic.fp_pipe_init_stages import (FPCordicInitStage,
                                                FPCordicConvertFixed)
from ieee754.cordic.sin_cos_pipe_stage import (CordicStage,
                                               CordicInitialStage)


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
                                       FPAddDeNormMod(self.pspec, False),
                                       FPCordicConvertFixed(self.pspec)])

        self.cordicstages = []

        initstage = CordicInitialStage(pspec)
        stages = []
        for i in range(pspec.iterations):
            stages.append(CordicStage(pspec, i))
        chunks = self.chunkify(initstage, stages)
        for chunk in chunks:
            chain = CordicPipeChain(pspec, chunk)
            self.cordicstages.append(chain)

        self._eqs = self.connect([self.denorm] + self.cordicstages)

    def chunkify(self, initstage, stages):
        chunks = []

        for i in range(0, len(stages), self.pspec.rounds_per_stage):
            chunks.append(stages[i:i + self.pspec.rounds_per_stage])
        chunks[0].insert(0, initstage)

        return chunks

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.denorm = self.denorm
        for i, stage in enumerate(self.cordicstages):
            setattr(m.submodules, "cordic%d" % i,
                    stage)
        m.d.comb += self._eqs
        return m

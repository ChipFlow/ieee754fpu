from nmutil.singlepipe import ControlBase
from nmutil.pipemodbase import PipeModBaseChain

from ieee754.cordic.sin_cos_pipe_stage import (
    CordicStage, CordicInitialStage)


class CordicPipeChain(PipeModBaseChain):
    def __init__(self, pspec, stages):
        self.stages = stages
        super().__init__(pspec)

    def get_chain(self):
        return self.stages


class CordicBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.pspec = pspec
        self.cordicstages = []
        initstage = CordicInitialStage(pspec)
        stages = []
        for i in range(pspec.iterations):
            stages.append(CordicStage(pspec, i))
        chunks = self.chunkify(initstage, stages)
        print(len(chunks))
        for chunk in chunks:
            chain = CordicPipeChain(pspec, chunk)
            self.cordicstages.append(chain)

        self._eqs = self.connect(self.cordicstages)

    def chunkify(self, initstage, stages):
        chunks = []

        for i in range(0, len(stages), self.pspec.rounds_per_stage):
            chunks.append(stages[i:i + self.pspec.rounds_per_stage])
        chunks[0].insert(0, initstage)

        return chunks

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        for i, stage in enumerate(self.cordicstages):
            setattr(m.submodules, "cordic%d" % i,
                    stage)
        m.d.comb += self._eqs
        return m

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
        self.cordicstages = []
        for i in range(pspec.iterations):
            if i == 0:
                stages = [CordicInitialStage(pspec), CordicStage(pspec, i)]
            else:
                stages = [CordicStage(pspec, i)]
            stage = CordicPipeChain(pspec, stages)
            self.cordicstages.append(stage)

        self._eqs = self.connect(self.cordicstages)

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        for i, stage in enumerate(self.cordicstages):
            setattr(m.submodules, "cordic%d" % i,
                    stage)
        m.d.comb += self._eqs
        return m

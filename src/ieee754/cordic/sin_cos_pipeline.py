from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits
from nmutil.pipemodbase import PipeModBaseChain

from ieee754.cordic.sin_cos_pipe_stage import (
    CordicStage, CordicInitialStage)
from ieee754.cordic.pipe_data import (CordicPipeSpec, CordicData,
                                      CordicInitialData)

class CordicPipeChain(PipeModBaseChain):
    def __init__(self, pspec, stages):
        self.stages = stages
        super().__init__(pspec)

    def get_chain(self):
        return self.stages
        

class CordicBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.initstage = CordicPipeChain(pspec,
                                         [CordicInitialStage(pspec)])
        self.cordicstages = []
        for i in range(pspec.iterations):
            stage = CordicPipeChain(pspec,
                                    [CordicStage(pspec, i)])
            self.cordicstages.append(stage)

        self._eqs = self.connect([self.initstage] + self.cordicstages)
        
    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.init = self.initstage
        for i, stage in enumerate(self.cordicstages):
            setattr(m.submodules, "cordic%d" % i,
                    stage)
        m.d.comb += self._eqs
        return m

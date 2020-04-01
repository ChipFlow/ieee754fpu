from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits
from nmutil.pipemodbase import PipeModBaseChain

from ieee754.cordic.sin_cos_pipe_stage import (
    CordicStage, CordicInitialStage)
from ieee754.cordic.pipe_data import (CordicPipeSpec, CordicData,
                                      CordicInitialData)

class CordicPipeChain(PipeModBaseChain):
    def get_chain(self):
        initstage = CordicInitialStage(self.pspec)
        cordicstages = []
        for i in range(self.pspec.iterations):
            stage = CordicStage(self.pspec, i)
            cordicstages.append(stage)
        return [initstage] + cordicstages
        

class CordicBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.chain = CordicPipeChain(pspec)
        self._eqs = self.connect([self.chain])
        
    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.chain = self.chain
        m.d.comb += self._eqs
        return m

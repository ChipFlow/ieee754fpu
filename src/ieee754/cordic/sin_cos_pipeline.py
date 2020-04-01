from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.cordic.sin_cos_pipe_stages import (
    CordicStage, CordicInitialStage)
from ieee754.cordic.pipe_data import (CordicPipeSpec, CordicData,
                                      CordicInitalData)

class CordicBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.init = CordicInitialStage(pspec)
        self.cordicstages = []
        for i in range(pspec.iterations):
            stage = CordicStage(pspec, i)
            self.cordicstages.append(stage)
        self._eqs = self.connect([self.init] + self.cordicstages)
        
    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.init = self.init
        for i, stage in enumerate(self.cordicstages):
            setattr(m.submodules, "stage%d" % i, stage)
        m.d.comb += self._eqs
        return m

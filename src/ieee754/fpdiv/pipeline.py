# IEEE Floating Point Divider Pipeline

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.normtopack import FPNormToPack
from .specialcases import FPDIVSpecialCasesDeNorm
from .divstages import FPDivStages



class FPDIVBasePipe(ControlBase):
    def __init__(self, width, id_wid):
        ControlBase.__init__(self)
        self.pipestart = FPDIVSpecialCasesDeNorm(width, id_wid)
        pipechain = []
        n_stages = 6 # TODO
        n_combinatorial_stages = 2 # TODO
        for i in range(n_stages):
            begin = i == 0 # needs to convert input from pipestart ospec
            end = i == n_stages - 1 # needs to convert output to pipeend ispec
            pipechain.append(FPDivStages(width, id_wid,
                                         n_combinatorial_stages,
                                         begin, end))
        self.pipechain = pipechain
        self.pipeend = FPNormToPack(width, id_wid)

        self._eqs = self.connect([self.pipestart] + pipechain + [self.pipeend])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.scnorm = self.pipestart
        for i, p in enumerate(self.pipechain):
            setattr(m.submodules, "pipediv%d" % i, p)
        m.submodules.normpack = self.pipeend
        m.d.comb += self._eqs
        return m


class FPDIVMuxInOut(ReservationStations):
    """ Reservation-Station version of FPDIV pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * N-stage divider pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """
    def __init__(self, width, num_rows):
        self.width = width
        self.id_wid = num_bits(width)
        self.alu = FPDIVBasePipe(width, self.id_wid)
        ReservationStations.__init__(self, num_rows)

    def i_specfn(self):
        return FPADDBaseData(self.width, self.id_wid)

    def o_specfn(self):
        return FPPackData(self.width, self.id_wid)

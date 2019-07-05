# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.normtopack import FPNormToPack
from .specialcases import FPMulSpecialCasesDeNorm
from .mulstages import FPMulStages



class FPMULBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.pipe1 = FPMulSpecialCasesDeNorm(pspec)
        self.pipe2 = FPMulStages(pspec)
        self.pipe3 = FPNormToPack(pspec)

        self._eqs = self.connect([self.pipe1, self.pipe2, self.pipe3])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.scnorm = self.pipe1
        m.submodules.mulstages = self.pipe2
        m.submodules.normpack = self.pipe3
        m.d.comb += self._eqs
        return m


class FPMULMuxInOut(ReservationStations):
    """ Reservation-Station version of FPMUL pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """
    def __init__(self, width, num_rows, op_wid=0):
        self.pspec = {}
        self.id_wid = num_bits(width)
        self.op_wid = op_wid
        self.pspec['id_wid'] = self.id_wid
        self.pspec['width'] = width
        self.pspec['op_wid'] = self.op_wid
        self.alu = FPMULBasePipe(self.pspec)
        ReservationStations.__init__(self, num_rows)

    def i_specfn(self):
        return FPADDBaseData(self.pspec)

    def o_specfn(self):
        return FPPackData(self.pspec)

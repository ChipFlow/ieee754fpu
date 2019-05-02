# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module
from nmigen.cli import main, verilog

from singlepipe import (ControlBase, SimpleHandshake, PassThroughStage)
from multipipe import CombMuxOutPipe
from multipipe import PriorityCombMuxInPipe

from fpcommon.getop import FPADDBaseData
from fpcommon.denorm import FPSCData
from fpcommon.pack import FPPackData
from fpcommon.normtopack import FPNormToPack
from fpadd.specialcases import FPAddSpecialCasesDeNorm
from fpadd.addstages import FPAddAlignSingleAdd

from concurrentunit import ReservationStations, num_bits


class FPADDBasePipe(ControlBase):
    def __init__(self, width, id_wid):
        ControlBase.__init__(self)
        self.pipe1 = FPAddSpecialCasesDeNorm(width, id_wid)
        self.pipe2 = FPAddAlignSingleAdd(width, id_wid)
        self.pipe3 = FPNormToPack(width, id_wid)

        self._eqs = self.connect([self.pipe1, self.pipe2, self.pipe3])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.scnorm = self.pipe1
        m.submodules.addalign = self.pipe2
        m.submodules.normpack = self.pipe3
        m.d.comb += self._eqs
        return m


class FPADDMuxInOut(ReservationStations):
    """ Reservation-Station version of FPADD pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 3-stage adder pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """
    def __init__(self, width, num_rows):
        self.width = width
        self.id_wid = num_bits(width)
        self.alu = FPADDBasePipe(width, self.id_wid)
        ReservationStations.__init__(self, num_rows)

    def i_specfn(self):
        return FPADDBaseData(self.width, self.id_wid)

    def o_specfn(self):
        return FPPackData(self.width, self.id_wid)

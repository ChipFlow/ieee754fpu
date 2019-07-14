# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import (ControlBase, SimpleHandshake, PassThroughStage)
from nmutil.multipipe import CombMuxOutPipe
from nmutil.multipipe import PriorityCombMuxInPipe
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.normtopack import FPNormToPack
from .specialcases import FPAddSpecialCasesDeNorm
from .addstages import FPAddAlignSingleAdd
from ieee754.pipeline import PipelineSpec


class FPADDBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.pipe1 = FPAddSpecialCasesDeNorm(pspec)
        self.pipe2 = FPAddAlignSingleAdd(pspec)
        self.pipe3 = FPNormToPack(pspec)

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

    def __init__(self, width, num_rows, op_wid=None):
        self.id_wid = num_bits(width)
        self.op_wid = op_wid
        self.pspec = PipelineSpec(width, self.id_wid, op_wid)
        self.alu = FPADDBasePipe(self.pspec)
        ReservationStations.__init__(self, num_rows)

    def i_specfn(self):
        return FPADDBaseData(self.pspec)

    def o_specfn(self):
        return FPPackData(self.pspec)

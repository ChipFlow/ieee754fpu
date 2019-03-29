# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux, Array, Const
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from singlepipe import (ControlBase, UnbufferedPipeline, PassThroughStage)
from multipipe import CombMuxOutPipe
from multipipe import PriorityCombMuxInPipe

from fpcommon.getop import FPADDBaseData
from fpcommon.denorm import FPSCData
from fpcommon.pack import FPPackData
from fpcommon.normtopack import FPNormToPack
from fpadd.specialcases import FPAddSpecialCasesDeNorm
from fpadd.addstages import FPAddAlignSingleAdd


class FPADDBasePipe(ControlBase):
    def __init__(self, width, id_wid):
        ControlBase.__init__(self)
        self.pipe1 = FPAddSpecialCasesDeNorm(width, id_wid)
        self.pipe2 = FPAddAlignSingleAdd(width, id_wid)
        self.pipe3 = FPNormToPack(width, id_wid)

        self._eqs = self.connect([self.pipe1, self.pipe2, self.pipe3])

    def elaborate(self, platform):
        m = Module()
        m.submodules.scnorm = self.pipe1
        m.submodules.addalign = self.pipe2
        m.submodules.normpack = self.pipe3
        m.d.comb += self._eqs
        return m


class FPADDInMuxPipe(PriorityCombMuxInPipe):
    def __init__(self, width, id_wid, num_rows):
        self.num_rows = num_rows
        def iospec(): return FPADDBaseData(width, id_wid)
        stage = PassThroughStage(iospec)
        PriorityCombMuxInPipe.__init__(self, stage, p_len=self.num_rows)


class FPADDMuxOutPipe(CombMuxOutPipe):
    def __init__(self, width, id_wid, num_rows):
        self.num_rows = num_rows
        def iospec(): return FPPackData(width, id_wid)
        stage = PassThroughStage(iospec)
        CombMuxOutPipe.__init__(self, stage, n_len=self.num_rows)


class FPADDMuxInOut:
    """ Reservation-Station version of FPADD pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 3-stage adder pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """
    def __init__(self, width, id_wid, num_rows):
        self.num_rows = num_rows
        self.inpipe = FPADDInMuxPipe(width, id_wid, num_rows)   # fan-in
        self.fpadd = FPADDBasePipe(width, id_wid)               # add stage
        self.outpipe = FPADDMuxOutPipe(width, id_wid, num_rows) # fan-out

        self.p = self.inpipe.p  # kinda annoying,
        self.n = self.outpipe.n # use pipe in/out as this class in/out
        self._ports = self.inpipe.ports() + self.outpipe.ports()

    def elaborate(self, platform):
        m = Module()
        m.submodules.inpipe = self.inpipe
        m.submodules.fpadd = self.fpadd
        m.submodules.outpipe = self.outpipe

        m.d.comb += self.inpipe.n.connect_to_next(self.fpadd.p)
        m.d.comb += self.fpadd.connect_to_next(self.outpipe)

        return m

    def ports(self):
        return self._ports



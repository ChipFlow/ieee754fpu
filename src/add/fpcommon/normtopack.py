# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux, Array, Const
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase, FPNumBase
from fpbase import MultiShiftRMerge, Trigger
from singlepipe import (ControlBase, StageChain, UnbufferedPipeline,
                        PassThroughStage)
from multipipe import CombMuxOutPipe
from multipipe import PriorityCombMuxInPipe

from fpbase import FPState, FPID
from fpcommon.postcalc import FPAddStage1Data
from fpcommon.postnormalise import FPNorm1ModSingle
from fpcommon.roundz import FPRoundMod
from fpcommon.corrections import FPCorrectionsMod
from fpcommon.pack import FPPackData, FPPackMod


class FPNormToPack(FPState, UnbufferedPipeline):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "normalise_1")
        self.id_wid = id_wid
        self.width = width
        UnbufferedPipeline.__init__(self, self) # pipeline is its own stage

    def ispec(self):
        return FPAddStage1Data(self.width, self.id_wid) # Norm1ModSingle ispec

    def ospec(self):
        return FPPackData(self.width, self.id_wid) # FPPackMod ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # Normalisation, Rounding Corrections, Pack - in a chain
        nmod = FPNorm1ModSingle(self.width, self.id_wid)
        rmod = FPRoundMod(self.width, self.id_wid)
        cmod = FPCorrectionsMod(self.width, self.id_wid)
        pmod = FPPackMod(self.width, self.id_wid)
        chain = StageChain([nmod, rmod, cmod, pmod])
        chain.setup(m, i)
        self.out_z = pmod.ospec()

        self.o = pmod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.out_z.eq(self.process(None))
        m.next = "pack_put_z"

# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

#from nmigen.cli import main, verilog

from nmutil.singlepipe import StageChain, SimpleHandshake

from ieee754.fpcommon.fpbase import FPState, FPID
from .postcalc import FPAddStage1Data
from .postnormalise import FPNorm1ModSingle
from .roundz import FPRoundMod
from .corrections import FPCorrectionsMod
from .pack import FPPackData, FPPackMod


class FPNormToPack(FPState, SimpleHandshake):

    def __init__(self, pspec, e_extra=False):
        FPState.__init__(self, "normalise_1")
        print ("normtopack", pspec)
        self.pspec = pspec
        self.e_extra = e_extra
        SimpleHandshake.__init__(self, self) # pipeline is its own stage

    def ispec(self):
        return FPAddStage1Data(self.pspec, e_extra=self.e_extra)

    def ospec(self):
        return FPPackData(self.pspec) # FPPackMod

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # Normalisation, Rounding Corrections, Pack - in a chain
        nmod = FPNorm1ModSingle(self.pspec, e_extra=self.e_extra)
        rmod = FPRoundMod(self.pspec)
        cmod = FPCorrectionsMod(self.pspec)
        pmod = FPPackMod(self.pspec)
        stages = [nmod, rmod, cmod, pmod]
        chain = StageChain(stages)
        chain.setup(m, i)
        self.out_z = pmod.ospec()

        self.o = pmod.o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.out_z.eq(self.process(None))
        m.next = "pack_put_z"

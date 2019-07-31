# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

#from nmigen.cli import main, verilog

from nmutil.singlepipe import StageChain

from ieee754.pipeline import DynamicPipe
from ieee754.fpcommon.postcalc import FPAddStage1Data
from ieee754.fpcommon.postnormalise import FPNorm1ModSingle
from ieee754.fpcommon.roundz import FPRoundMod
from ieee754.fpcommon.corrections import FPCorrectionsMod
from ieee754.fpcommon.pack import FPPackData, FPPackMod


class FPNormToPack(DynamicPipe):

    def __init__(self, pspec, e_extra=False):
        #print ("normtopack", pspec)
        self.pspec = pspec
        self.e_extra = e_extra
        super().__init__(pspec)

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

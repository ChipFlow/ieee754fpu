# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

#from nmigen.cli import main, verilog

from nmutil.singlepipe import StageChain

from ieee754.fpcommon.modbase import FPModBaseChain
from ieee754.fpcommon.postcalc import FPAddStage1Data
from ieee754.fpcommon.postnormalise import FPNorm1ModSingle
from ieee754.fpcommon.roundz import FPRoundMod
from ieee754.fpcommon.corrections import FPCorrectionsMod
from ieee754.fpcommon.pack import FPPackData, FPPackMod


class FPNormToPack(FPModBaseChain):

    def __init__(self, pspec, e_extra=False):
        self.e_extra = e_extra
        super().__init__(pspec)

    def get_chain(self):
        """ gets chain of modules
        """
        # Normalisation, Rounding Corrections, Pack - in a chain
        nmod = FPNorm1ModSingle(self.pspec, e_extra=self.e_extra)
        rmod = FPRoundMod(self.pspec)
        cmod = FPCorrectionsMod(self.pspec)
        pmod = FPPackMod(self.pspec)

        return [nmod, rmod, cmod, pmod]

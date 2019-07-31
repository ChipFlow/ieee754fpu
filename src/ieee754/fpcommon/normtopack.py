"""IEEE754 Floating Point Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmutil.pipemodbase import PipeModBaseChain
from ieee754.fpcommon.postnormalise import FPNorm1ModSingle
from ieee754.fpcommon.roundz import FPRoundMod
from ieee754.fpcommon.corrections import FPCorrectionsMod
from ieee754.fpcommon.pack import FPPackMod


class FPNormToPack(PipeModBaseChain):

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

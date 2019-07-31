"""IEEE754 Floating Point Adder Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import StageChain
from ieee754.pipeline import DynamicPipe

from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPAddStage1Data
from ieee754.fpadd.align import FPAddAlignSingleMod
from ieee754.fpadd.add0 import FPAddStage0Mod
from ieee754.fpadd.add1 import FPAddStage1Mod


class FPAddAlignSingleAdd(DynamicPipe):

    def __init__(self, pspec):
        self.pspec = pspec
        super().__init__(pspec)

    def ispec(self):
        return FPSCData(self.pspec, True)

    def ospec(self):
        return FPAddStage1Data(self.pspec) # AddStage1 ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # chain AddAlignSingle, AddStage0 and AddStage1
        mod = FPAddAlignSingleMod(self.pspec)
        a0mod = FPAddStage0Mod(self.pspec)
        a1mod = FPAddStage1Mod(self.pspec)

        chain = StageChain([mod, a0mod, a1mod])
        chain.setup(m, i)

        self.o = a1mod.o

    def process(self, i):
        return self.o


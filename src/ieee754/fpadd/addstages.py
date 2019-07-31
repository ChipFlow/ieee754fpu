"""IEEE754 Floating Point Adder Pipeline

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

"""

from nmutil.pipemodbase import PipeModBaseChain

from ieee754.fpadd.align import FPAddAlignSingleMod
from ieee754.fpadd.add0 import FPAddStage0Mod
from ieee754.fpadd.add1 import FPAddStage1Mod


class FPAddAlignSingleAdd(PipeModBaseChain):

    def get_chain(self):
        # chain AddAlignSingle, AddStage0 and AddStage1
        mod = FPAddAlignSingleMod(self.pspec)
        a0mod = FPAddStage0Mod(self.pspec)
        a1mod = FPAddStage1Mod(self.pspec)

        return [mod, a0mod, a1mod]

"""IEEE754 Floating Point pipelined Divider

Relevant bugreport: http://bugs.libre-riscv.org/show_bug.cgi?id=99

"""

from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import (StageChain, SimpleHandshake)

from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.denorm import FPSCData
from ieee754.fpcommon.postcalc import FPAddStage1Data

# TODO: write these
from .div0 import FPDivStage0Mod
from .div1 import FPDivStage1Mod
from .div2 import FPDivStage2Mod
from .div0 import FPDivStage0Data


class FPDivStages(FPState, SimpleHandshake):

    def __init__(self, width, pspec, n_stages, begin, end):
        FPState.__init__(self, "align")
        self.width = width
        self.pspec = pspec
        self.n_stages = n_stages # number of combinatorial stages
        self.begin = begin # "begin" mode
        self.end = end # "end" mode
        SimpleHandshake.__init__(self, self) # pipeline is its own stage
        self.m1o = self.ospec()

    def ispec(self):
        if self.begin: # TODO - this is for FPDivStage0Mod
            # REQUIRED.  do NOT change.
            return FPSCData(self.width, self.pspec, False) # from denorm

        if self.end: # TODO - this is for FPDivStage2Mod
            # XXX TODO: replace with "intermediary" (DivPipeCoreInterstageData?)
            return FPDivStage0Data(self.width, self.pspec) # DIV ispec (loop)

        # TODO - this is for FPDivStage1Mod
        # XXX TODO: replace with "intermediary" (DivPipeCoreInterstageData)
        return FPDivStage0Data(self.width, self.pspec) # DIV ispec (loop)

    def ospec(self):
        if self.begin: # TODO - this is for FPDivStage0Mod
            # XXX TODO: replace with "intermediary" (DivPipeCoreInterstageData)
            return FPDivStage0Data(self.width, self.pspec) # DIV ospec (loop)

        if self.end: # TODO - this is for FPDivStage2Mod
            # REQUIRED.  do NOT change.
            return FPAddStage1Data(self.width, self.pspec) # to post-norm

        # TODO - this is for FPDivStage1Mod
        # XXX TODO: replace with "intermediary" (DivPipeCoreInterstageData)
        return FPDivStage0Data(self.width, self.pspec) # DIV ospec (loop)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """

        # start mode accepts data from the FP normalisation stage
        # and does a bit of munging of the data.  it will be chained
        # into the first DIV combinatorial block,

        # end mode takes the DIV pipeline/chain data and munges it
        # into the format that the normalisation can accept.

        # neither start nor end mode simply takes the exact same
        # data in as out, this is where the Q/Rem comes in and Q/Rem goes out

        divstages = []

        if self.begin: # XXX check this
            divstages.append(FPDivStage0Mod(self.width, self.pspec))

        for count in range(self.n_stages): # number of combinatorial stages
            divstages.append(FPDivStage1Mod(self.width, self.pspec))

        if self.end: # XXX check this
            divstages.append(FPDivStage2Mod(self.width, self.pspec))

        chain = StageChain(divstages)
        chain.setup(m, i)

        # output is from the last pipe stage
        self.o = divstages[-1].o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.m1o.eq(self.process(None))
        m.next = "normalise_1"



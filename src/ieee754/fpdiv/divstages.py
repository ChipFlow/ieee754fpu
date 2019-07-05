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
from .div1 import FPDivStage1Mod # can be dropped entirely
                                 # (replaced with DivPipeCalculateStage)
                                 # note, yes, DivPipeCalculateStage *NOT*
                                 # DivPipeCoreCalculateStage
from .div2 import FPDivStage2Mod
from .div0 import FPDivStage0Data


class FPDivStagesSetup(FPState, SimpleHandshake):

    def __init__(self, pspec, n_stages):
        FPState.__init__(self, "divsetup")
        self.pspec = pspec
        self.n_stages = n_stages # number of combinatorial stages
        SimpleHandshake.__init__(self, self) # pipeline is its own stage
        self.m1o = self.ospec()

    def ispec(self):
        # REQUIRED.  do NOT change.
        return FPSCData(self.pspec, False) # from denorm

    def ospec(self):
        # XXX TODO: replace with "intermediary" (DivPipeInterstageData)
        return FPDivStage0Data(self.pspec) # DIV ospec (loop)

    def setup(self, m, i):
        """ links module to inputs and outputs.

            note: this is a pure *combinatorial* module (StageChain).
            therefore each sub-module must also be combinatorial
            (and not do too much: in particular, n_stages must be
            reduced slightly when either self.end=True or self.begin=True)
        """

        divstages = []

        # Converts from FPSCData into DivPipeInputData
        divstages.append(FPDivStage0Mod(self.pspec))

        # does 1 "convert" (actual processing) from DivPipeInputData
        # into "intermediate" output (DivPipeInterstageData)
        # vvvvvvv
        # FIXME divstages.append(DivPipeSetupStage(something))
        # ^^^^^^^

        # here is where the intermediary stages are added.
        # n_stages is adjusted (in pipeline.py), reduced to take
        # into account the extra processing that self.begin and self.end
        # will add.
        for count in range(self.n_stages): # number of combinatorial stages
            # XXX: this can actually be entirely dropped...
            divstages.append(FPDivStage1Mod(self.pspec))

            # ... and replaced with this.
            # vvvvvvv
            #divstages.append(DivPipeCalculateStage(core_config, count))
            # ^^^^^^^

        chain = StageChain(divstages)
        chain.setup(m, i)

        # output is from the last pipe stage
        self.o = divstages[-1].o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.m1o.eq(self.process(None))
        m.next = "normalise_1"


class FPDivStagesIntermediary(FPState, SimpleHandshake):

    def __init__(self, pspec, n_stages):
        FPState.__init__(self, "divintermediate")
        self.pspec = pspec
        self.n_stages = n_stages # number of combinatorial stages
        SimpleHandshake.__init__(self, self) # pipeline is its own stage
        self.m1o = self.ospec()

    def ispec(self):
        # TODO - this is for FPDivStage1Mod
        # XXX TODO: replace with "intermediary" (DivPipeInterstageData)
        return FPDivStage0Data(self.pspec) # DIV ispec (loop)

    def ospec(self):
        # TODO - this is for FPDivStage1Mod
        # XXX TODO: replace with "intermediary" (DivPipeInterstageData)
        return FPDivStage0Data(self.pspec) # DIV ospec (loop)

    def setup(self, m, i):
        """ links module to inputs and outputs.

            note: this is a pure *combinatorial* module (StageChain).
            therefore each sub-module must also be combinatorial
            (and not do too much)
        """

        divstages = []

        # here is where the intermediary stages are added.
        # n_stages is adjusted (in pipeline.py), reduced to take
        # into account the extra processing that self.begin and self.end
        # will add.
        for count in range(self.n_stages): # number of combinatorial stages
            # XXX: this can actually be entirely dropped...
            divstages.append(FPDivStage1Mod(self.pspec))

            # ... and replaced with this.
            # vvvvvvv
            #divstages.append(DivPipeCalculateStage(core_config, count))
            # ^^^^^^^

        chain = StageChain(divstages)
        chain.setup(m, i)

        # output is from the last pipe stage
        self.o = divstages[-1].o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.m1o.eq(self.process(None))
        m.next = "normalise_1"


class FPDivStagesFinal(FPState, SimpleHandshake):

    def __init__(self, pspec, n_stages):
        FPState.__init__(self, "divfinal")
        self.pspec = pspec
        self.n_stages = n_stages # number of combinatorial stages
        SimpleHandshake.__init__(self, self) # pipeline is its own stage
        self.m1o = self.ospec()

    def ispec(self):
        # XXX TODO: replace with "intermediary" (DivPipeInterstageData?)
        return FPDivStage0Data(self.pspec) # DIV ispec (loop)

    def ospec(self):
        # REQUIRED.  do NOT change.
        return FPAddStage1Data(self.pspec) # to post-norm

    def setup(self, m, i):
        """ links module to inputs and outputs.

            note: this is a pure *combinatorial* module (StageChain).
            therefore each sub-module must also be combinatorial
            (and not do too much)
        """

        # takes the DIV pipeline/chain data and munges it
        # into the format that the normalisation can accept.

        divstages = []

        # here is where the intermediary stages are added.
        # n_stages is adjusted (in pipeline.py), reduced to take
        # into account the extra processing that self.begin and self.end
        # will add.
        for count in range(self.n_stages): # number of combinatorial stages
            # XXX: this can actually be entirely dropped...
            divstages.append(FPDivStage1Mod(self.pspec))

            # ... and replaced with this.
            # vvvvvvv
            #divstages.append(DivPipeCalculateStage(core_config, count))
            # ^^^^^^^

        # does the final conversion from intermediary to output data
        # vvvvvvv
        # FIXME divstages.append(DivPipeFinalStage(something))
        # ^^^^^^^

        # does conversion from DivPipeOutputData into
        # FPAddStage1Data format (bad name, TODO, doesn't matter),
        # so that post-normalisation and corrections can take over
        divstages.append(FPDivStage2Mod(self.pspec))

        chain = StageChain(divstages)
        chain.setup(m, i)

        # output is from the last pipe stage
        self.o = divstages[-1].o

    def process(self, i):
        return self.o

    def action(self, m):
        m.d.sync += self.m1o.eq(self.process(None))
        m.next = "normalise_1"



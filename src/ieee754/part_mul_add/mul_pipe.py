# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
"""Integer Multiplication."""

from nmigen import Signal, Module, Value, Elaboratable, Cat, C, Mux, Repl
from nmigen.cli import main

from ieee754.part_mul_add.multiply import (InputData, OutputData,
                                           AllTerms, AddReduceInternal,
                                           Intermediates, FinalOut)
                                            
from nmutil.pipemodbase import PipeModBaseChain
from nmutil.singlepipe import ControlBase
from ieee754.pipeline import PipelineSpec


class MulStages(PipeModBaseChain):

    def __init__(self, pspec, part_pts):
        self.part_pts = part_pts
        super().__init__(pspec)

    def get_chain(self):
        # chain AddReduce, Intermediates and FinalOut
        part_pts = self.part_pts
        n_inputs = 64 + 4
        at = AddReduceInternal(self.pspec, n_inputs, part_pts, partition_step=2)
        levels = at.levels

        interm = Intermediates(self.pspec, part_pts)
        finalout = FinalOut(self.pspec, part_pts)
        self.output = finalout.o.output

        return levels + [interm, finalout]


class AllTermsPipe(PipeModBaseChain):

    def __init__(self, pspec, n_inputs):
        self.n_inputs = n_inputs
        super().__init__(pspec)

    def get_chain(self):
        """ gets module
        """
        nmod = AllTerms(self.pspec, self.n_inputs)

        return [nmod]


class MulPipe_8_16_32_64(ControlBase):
    """Signed/Unsigned 8/16/32/64-bit partitioned integer multiplier pipeline
    """

    def __init__(self):
        """ register_levels: specifies the points in the cascade at which
            flip-flops are to be inserted.
        """

        self.id_wid = 0 # num_bits(num_rows)
        self.op_wid = 0
        self.pspec = PipelineSpec(64, self.id_wid, self.op_wid, n_ops=3)
        self.pspec.n_parts = 8

        ControlBase.__init__(self)

        n_inputs = 64 + 4
        self.allterms = AllTermsPipe(self.pspec, n_inputs)
        stage = self.allterms.chain[0]
        part_pts = stage.i.part_pts
        self.mulstages = MulStages(self.pspec, part_pts)

        self._eqs = self.connect([self.allterms, self.mulstages])

        self.a = stage.i.a
        self.b = stage.i.b
        self.output = self.mulstages.output

    def ispec(self):
        return InputData()

    def ospec(self):
        return OutputData()

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)

        m.submodules.allterms = self.allterms
        m.submodules.mulstages = self.mulstages
        m.d.comb += self._eqs

        return m


if __name__ == "__main__":
    m = MulPipe_8_16_32_64()
    main(m, ports=[m.a,
                   m.b,
                   m.output,
                   ])

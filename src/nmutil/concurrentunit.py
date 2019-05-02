""" concurrent unit from mitch alsup augmentations to 6600 scoreboard

    * data fans in
    * data goes through a pipeline
    * results fan back out.

    the output data format has to have a member "mid", which is used
    as the array index on fan-out
"""

from math import log
from nmigen import Module
from nmigen.cli import main, verilog

from nmutil.singlepipe import PassThroughStage
from nmutil.multipipe import CombMuxOutPipe
from nmutil.multipipe import PriorityCombMuxInPipe


def num_bits(n):
    return int(log(n) / log(2))


class FPADDInMuxPipe(PriorityCombMuxInPipe):
    def __init__(self, num_rows, iospecfn):
        self.num_rows = num_rows
        stage = PassThroughStage(iospecfn)
        PriorityCombMuxInPipe.__init__(self, stage, p_len=self.num_rows)


class FPADDMuxOutPipe(CombMuxOutPipe):
    def __init__(self, num_rows, iospecfn):
        self.num_rows = num_rows
        stage = PassThroughStage(iospecfn)
        CombMuxOutPipe.__init__(self, stage, n_len=self.num_rows)


class ReservationStations:
    """ Reservation-Station pipeline

        Input: num_rows - number of input and output Reservation Stations

        Requires: the addition of an "alu" object, an i_specfn and an o_specfn

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * ALU pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """
    def __init__(self, num_rows):
        self.num_rows = num_rows
        self.inpipe = FPADDInMuxPipe(num_rows, self.i_specfn)   # fan-in
        self.outpipe = FPADDMuxOutPipe(num_rows, self.o_specfn) # fan-out

        self.p = self.inpipe.p  # kinda annoying,
        self.n = self.outpipe.n # use pipe in/out as this class in/out
        self._ports = self.inpipe.ports() + self.outpipe.ports()

    def elaborate(self, platform):
        m = Module()
        m.submodules.inpipe = self.inpipe
        m.submodules.alu = self.alu
        m.submodules.outpipe = self.outpipe

        m.d.comb += self.inpipe.n.connect_to_next(self.alu.p)
        m.d.comb += self.alu.connect_to_next(self.outpipe)

        return m

    def ports(self):
        return self._ports



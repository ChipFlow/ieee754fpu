# IEEE754 FCLASS Module
# Copyright (C) 2019 Luke Kenneth Casson Leighon <lkcl@lkcl.net>


from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.pack import FPPackData


from ieee754.fpcommon.fpbase import FPState, FPNumBase
from ieee754.fpcommon.getop import FPPipeContext

from nmutil.singlepipe import SimpleHandshake, StageChain

from ieee754.fpcommon.fpbase import FPState
from ieee754.fclass.fclass import FPClassMod
from ieee754.pipeline import PipelineSpec


class FPFClassPipe(FPState, SimpleHandshake):
    """ FPConversion and De-norm
    """

    def __init__(self, modkls, in_pspec, out_pspec):
        FPState.__init__(self, "cvt")
        sc = modkls(in_pspec, out_pspec)
        SimpleHandshake.__init__(self, sc)
        self.out = self.ospec(None)


# XXX not used because there isn't anything to "join" (no pipe chain)
# keeping this code around just in case FPClass has to be split into
# two [unlikely but hey]
class FPClassBasePipe(ControlBase):
    def __init__(self, modkls, in_pspec, out_pspec):
        ControlBase.__init__(self)
        # redundant because there's only one "thing" here.
        self.pipe1 = FPFClassPipe(modkls, in_pspec, out_pspec)
        self._eqs = self.connect([self.pipe1, ])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.fclass = self.pipe1
        m.d.comb += self._eqs
        return m


class FPClassMuxInOutBase(ReservationStations):
    """ Reservation-Station version of FPClass pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, modkls, in_width, out_width,
                       num_rows, op_wid=0, pkls=FPClassBasePipe):
        self.op_wid = op_wid
        self.id_wid = num_bits(in_width)
        self.out_id_wid = num_bits(out_width)

        self.in_pspec = PipelineSpec(in_width, self.id_wid, self.op_wid)
        self.out_pspec = PipelineSpec(out_width, self.out_id_wid, op_wid)

        self.alu = pkls(modkls, self.in_pspec, self.out_pspec)
        ReservationStations.__init__(self, num_rows)

    def i_specfn(self):
        return FPADDBaseData(self.in_pspec)

    def o_specfn(self):
        return FPPackData(self.out_pspec)


class FPClassMuxInOut(FPClassMuxInOutBase):
    """ Reservation-Station version of FPClass pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, in_width, out_width, num_rows, op_wid=0):
        FPClassMuxInOutBase.__init__(self, FPClassMod,
                                         in_width, out_width,
                                         num_rows, op_wid,
                                         pkls=FPFClassPipe)
                                         #pkls=FPClassBasePipe)


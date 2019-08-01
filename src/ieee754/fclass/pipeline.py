# IEEE754 FCLASS Module
# Copyright (C) 2019 Luke Kenneth Casson Leighon <lkcl@lkcl.net>

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits
from ieee754.fpcommon.fpbase import FPNumBase
from ieee754.fclass.fclass import FPClassMod
from ieee754.pipeline import PipelineSpec, DynamicPipe


class FPFClassPipe(DynamicPipe):
    """ FPConversion: turns its argument (modkls) from a stage into a pipe
    """

    def __init__(self, in_pspec, out_pspec, modkls):
        in_pspec.stage = modkls(in_pspec, out_pspec)
        super().__init__(in_pspec)


# XXX not used because there isn't anything to "join" (no pipe chain)
# keeping this code around just in case FPClass has to be split into
# two [unlikely but hey]
class FPClassBasePipe(ControlBase):
    def __init__(self, modkls, in_pspec, out_pspec):
        ControlBase.__init__(self)
        # redundant because there's only one "thing" here.
        self.pipe1 = FPFClassPipe(in_pspec, out_pspec, modkls)
        self._eqs = self.connect([self.pipe1, ])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.fclass = self.pipe1
        m.d.comb += self._eqs
        return m


class FPClassMuxInOutBase(ReservationStations):
    """ Reservation-Station version of FPClass pipeline.

        * fan-in on inputs (an array of FPBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, modkls, in_width, out_width,
                       num_rows, op_wid=0, pkls=FPClassBasePipe):
        self.op_wid = op_wid
        self.id_wid = num_bits(num_rows)

        self.in_pspec = PipelineSpec(in_width, self.id_wid, op_wid)
        self.out_pspec = PipelineSpec(out_width, self.id_wid, op_wid)

        self.alu = pkls(self.in_pspec, self.out_pspec, modkls)
        ReservationStations.__init__(self, num_rows)


class FPClassMuxInOut(FPClassMuxInOutBase):
    """ Reservation-Station version of FPClass pipeline.

        * fan-in on inputs (an array of FPBaseData: a,b,mid)
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


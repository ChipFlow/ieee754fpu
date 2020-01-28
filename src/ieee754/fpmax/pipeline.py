"""IEEE754 Floating Point Conversion

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

"""

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.pipeline import PipelineSpec, DynamicPipe

from ieee754.fpmax.fpmax import FPMAXPipeMod


class FPMAXStage(DynamicPipe):
    """ FPConversion and De-norm
    """

    def __init__(self, in_pspec):
        stage = FPMAXPipeMod(in_pspec)
        in_pspec.stage = stage
        super().__init__(in_pspec)


class FPMAXBasePipe(ControlBase):
    def __init__(self, pspec):
        ControlBase.__init__(self)
        self.pipe1 = FPMAXStage(pspec)
        self._eqs = self.connect([self.pipe1, ])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.fpmax = self.pipe1
        m.d.comb += self._eqs
        return m


class FPMAXMuxInOut(ReservationStations):
    """ Reservation-Station version of FPCVT pipeline.

        * fan-in on inputs (an array of FPBaseData: a,b,mid)
        * converter pipeline (alu)
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, in_width, num_rows, op_wid=1):
        self.op_wid = op_wid
        self.id_wid = num_bits(num_rows)

        self.in_pspec = PipelineSpec(in_width, self.id_wid, self.op_wid)

        self.alu = FPMAXBasePipe(self.in_pspec)
        ReservationStations.__init__(self, num_rows)

# IEEE754 Floating Point Conversion
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>


import sys
import functools

from nmigen import Module, Signal, Cat, Const, Mux, Elaboratable
from nmigen.cli import main, verilog

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.normtopack import FPNormToPack


from nmigen import Module, Signal, Elaboratable
from math import log

from ieee754.fpcommon.getop import FPPipeContext

from nmutil.singlepipe import SimpleHandshake, StageChain

from ieee754.fpcommon.fpbase import FPState
from ieee754.pipeline import PipelineSpec

from ieee754.fcvt.float2int import FPCVTFloatToIntMod
from ieee754.fcvt.int2float import FPCVTIntToFloatMod
from ieee754.fcvt.upsize import FPCVTUpConvertMod
from ieee754.fcvt.downsize import FPCVTDownConvertMod


class SignedOp:
    def __init__(self):
        self.signed = Signal(reset_less=True)

    def eq(self, i):
        return [self.signed.eq(i)]


class FPCVTConvertDeNorm(FPState, SimpleHandshake):
    """ FPConversion and De-norm
    """

    def __init__(self, modkls, in_pspec, out_pspec):
        FPState.__init__(self, "cvt")
        sc = modkls(in_pspec, out_pspec)
        SimpleHandshake.__init__(self, sc)
        self.out = self.ospec(None)


class FPCVTFtoIntBasePipe(ControlBase):
    def __init__(self, modkls, e_extra, in_pspec, out_pspec):
        ControlBase.__init__(self)
        self.pipe1 = FPCVTConvertDeNorm(modkls, in_pspec, out_pspec)
        #self.pipe2 = FPNormToPack(out_pspec, e_extra=e_extra)

        #self._eqs = self.connect([self.pipe1, self.pipe2])
        self._eqs = self.connect([self.pipe1, ])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.down = self.pipe1
        #m.submodules.normpack = self.pipe2
        m.d.comb += self._eqs
        return m


class FPCVTBasePipe(ControlBase):
    def __init__(self, modkls, e_extra, in_pspec, out_pspec):
        ControlBase.__init__(self)
        self.pipe1 = FPCVTConvertDeNorm(modkls, in_pspec, out_pspec)
        self.pipe2 = FPNormToPack(out_pspec, e_extra=e_extra)

        self._eqs = self.connect([self.pipe1, self.pipe2])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.down = self.pipe1
        m.submodules.normpack = self.pipe2
        m.d.comb += self._eqs
        return m


class FPCVTMuxInOutBase(ReservationStations):
    """ Reservation-Station version of FPCVT pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, modkls, e_extra, in_width, out_width,
                       num_rows, op_wid=0, pkls=FPCVTBasePipe):
        self.op_wid = op_wid
        self.id_wid = num_bits(in_width)
        self.out_id_wid = num_bits(out_width)

        self.in_pspec = PipelineSpec(in_width, self.id_wid, self.op_wid)
        self.out_pspec = PipelineSpec(out_width, self.out_id_wid, op_wid)

        self.alu = pkls(modkls, e_extra, self.in_pspec, self.out_pspec)
        ReservationStations.__init__(self, num_rows)

    def i_specfn(self):
        return FPADDBaseData(self.in_pspec)

    def o_specfn(self):
        return FPPackData(self.out_pspec)


def getkls(*args, **kwargs):
    print ("getkls", args, kwargs)
    return FPCVTMuxInOutBase(*args, **kwargs)


# factory which creates near-identical class structures that differ by
# the module and the e_extra argument.  at some point it would be good
# to merge these into a single dynamic "thing" that takes an operator.
# however, the difference(s) in the bitwidths makes that a little less
# straightforward.
muxfactoryinput = [("FPCVTDownMuxInOut", FPCVTDownConvertMod, True, ),
                   ("FPCVTUpMuxInOut",   FPCVTUpConvertMod,   False, ),
                   ("FPCVTIntMuxInOut",   FPCVTIntToFloatMod,   True, ),
                  ]

for (name, kls, e_extra) in muxfactoryinput:
    fn = functools.partial(getkls, kls, e_extra)
    setattr(sys.modules[__name__], name, fn)


class FPCVTF2IntMuxInOut(FPCVTMuxInOutBase):
    """ Reservation-Station version of FPCVT pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, in_width, out_width, num_rows, op_wid=0):
        FPCVTMuxInOutBase.__init__(self, FPCVTFloatToIntMod, False,
                                         in_width, out_width,
                                         num_rows, op_wid,
                                         pkls=FPCVTFtoIntBasePipe)


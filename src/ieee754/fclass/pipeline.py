# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

import sys
import functools

from nmigen import Module, Signal, Cat, Const, Mux, Elaboratable
from nmigen.cli import main, verilog

from nmutil.singlepipe import ControlBase
from nmutil.concurrentunit import ReservationStations, num_bits

from ieee754.fpcommon.fpbase import Overflow
from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.normtopack import FPNormToPack
from ieee754.fpcommon.postcalc import FPAddStage1Data
from ieee754.fpcommon.msbhigh import FPMSBHigh
from ieee754.fpcommon.exphigh import FPEXPHigh


from nmigen import Module, Signal, Elaboratable
from math import log

from ieee754.fpcommon.fpbase import FPNumIn, FPNumOut, FPNumBaseRecord
from ieee754.fpcommon.fpbase import FPState, FPNumBase
from ieee754.fpcommon.getop import FPPipeContext

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from nmutil.singlepipe import SimpleHandshake, StageChain

from ieee754.fpcommon.fpbase import FPState
from ieee754.pipeline import PipelineSpec


class FPClassMod(Elaboratable):
    """ obtains floating point information (zero, nan, inf etc.)
    """
    def __init__(self, in_pspec, out_pspec):
        self.in_pspec = in_pspec
        self.out_pspec = out_pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.in_pspec)

    def ospec(self):
        return FPPackData(self.out_pspec)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.upconvert = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        # decode incoming FP number
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        a1 = FPNumBaseRecord(self.in_pspec.width, False)
        print("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.d.comb += a1.v.eq(self.i.a)

        # FCLASS: work out the "type" of the FP number

        finite_nzero = Signal(reset_less=True)
        m.d.comb += finite_nzero.eq(~a1.is_nan & ~a1.is_inf & ~a1.is_zero)
        subnormal = a1.exp_lt_n126

        m.d.comb += self.o.z.eq(Cat(
                    a1.s   & a1.is_inf,                 # | −inf.
                    a1.s   & finite_nzero & ~subnormal, # | -normal number.
                    a1.s   & finite_nzero &  subnormal, # | -subnormal number.
                    a1.s & a1.is_zero,                  # | −0.
                    ~a1.s & a1.is_zero,                 # | +0.
                    ~a1.s & finite_nzero &  subnormal,  # | +subnormal number.
                    ~a1.s & finite_nzero & ~subnormal,  # | +normal number.
                    ~a1.s & a1.is_inf,                  # | +inf.
                    a1.is_denormalised,                 # | a signaling NaN.
                    a1.is_nan & ~a1.is_denormalised))   # | a quiet NaN

        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPFClassPipe(FPState, SimpleHandshake):
    """ FPConversion and De-norm
    """

    def __init__(self, modkls, in_pspec, out_pspec):
        FPState.__init__(self, "cvt")
        sc = modkls(in_pspec, out_pspec)
        SimpleHandshake.__init__(self, sc)
        self.out = self.ospec(None)


class FPClassBasePipe(ControlBase):
    def __init__(self, modkls, e_extra, in_pspec, out_pspec):
        ControlBase.__init__(self)
        self.pipe1 = FPFClassPipe(modkls, in_pspec, out_pspec)
        self._eqs = self.connect([self.pipe1, ])

    def elaborate(self, platform):
        m = ControlBase.elaborate(self, platform)
        m.submodules.down = self.pipe1
        m.d.comb += self._eqs
        return m




class FPClassMuxInOutBase(ReservationStations):
    """ Reservation-Station version of FPClass pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, modkls, e_extra, in_width, out_width,
                       num_rows, op_wid=0, pkls=FPClassBasePipe):
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


class FPClassMuxInOut(FPClassMuxInOutBase):
    """ Reservation-Station version of FPClass pipeline.

        * fan-in on inputs (an array of FPADDBaseData: a,b,mid)
        * 2-stage multiplier pipeline
        * fan-out on outputs (an array of FPPackData: z,mid)

        Fan-in and Fan-out are combinatorial.
    """

    def __init__(self, in_width, out_width, num_rows, op_wid=0):
        FPClassMuxInOutBase.__init__(self, FPClassMod, False,
                                         in_width, out_width,
                                         num_rows, op_wid,
                                         pkls=FPClassBasePipe)


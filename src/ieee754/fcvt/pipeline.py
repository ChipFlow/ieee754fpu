# IEEE754 Floating Point Conversion
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>


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

from ieee754.fcvt.float2int import FPCVTFloatToIntMod
from ieee754.fcvt.int2float import FPCVTIntToFloatMod
from ieee754.fcvt.upsize import FPCVTUpConvertMod


class SignedOp:
    def __init__(self):
        self.signed = Signal(reset_less=True)

    def eq(self, i):
        return [self.signed.eq(i)]


class FPCVTDownConvertMod(Elaboratable):
    """ FP down-conversion (higher to lower bitwidth)
    """
    def __init__(self, in_pspec, out_pspec):
        self.in_pspec = in_pspec
        self.out_pspec = out_pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.in_pspec)

    def ospec(self):
        return FPAddStage1Data(self.out_pspec, e_extra=True)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.downconvert = self
        comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        a1 = FPNumBaseRecord(self.in_pspec.width, False)
        print("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        comb += a1.v.eq(self.i.a)
        z1 = self.o.z
        print("z1", z1.width, z1.rmw, z1.e_width, z1.e_start, z1.e_end)

        me = a1.rmw
        ms = a1.rmw - self.o.z.rmw
        print("ms-me", ms, me)

        # intermediaries
        exp_sub_n126 = Signal((a1.e_width, True), reset_less=True)
        exp_gt127 = Signal(reset_less=True)
        # constants from z1, at the bit-width of a1.
        N126 = Const(z1.fp.N126.value, (a1.e_width, True))
        P127 = Const(z1.fp.P127.value, (a1.e_width, True))
        comb += exp_sub_n126.eq(a1.e - N126)
        comb += exp_gt127.eq(a1.e > P127)

        # if a zero, return zero (signed)
        with m.If(a1.exp_n127):
            comb += self.o.z.zero(a1.s)
            comb += self.o.out_do_z.eq(1)

        # if a range outside z's min range (-126)
        with m.Elif(exp_sub_n126 < 0):
            comb += self.o.of.guard.eq(a1.m[ms-1])
            comb += self.o.of.round_bit.eq(a1.m[ms-2])
            comb += self.o.of.sticky.eq(a1.m[:ms-2].bool())
            comb += self.o.of.m0.eq(a1.m[ms])  # bit of a1

            comb += self.o.z.s.eq(a1.s)
            comb += self.o.z.e.eq(a1.e)
            comb += self.o.z.m.eq(a1.m[-self.o.z.rmw-1:])
            comb += self.o.z.m[-1].eq(1)

        # if a is inf return inf
        with m.Elif(a1.is_inf):
            comb += self.o.z.inf(a1.s)
            comb += self.o.out_do_z.eq(1)

        # if a is NaN return NaN
        with m.Elif(a1.is_nan):
            comb += self.o.z.nan(0)
            comb += self.o.out_do_z.eq(1)

        # if a mantissa greater than 127, return inf
        with m.Elif(exp_gt127):
            print("inf", self.o.z.inf(a1.s))
            comb += self.o.z.inf(a1.s)
            comb += self.o.out_do_z.eq(1)

        # ok after all that, anything else should fit fine (whew)
        with m.Else():
            comb += self.o.of.guard.eq(a1.m[ms-1])
            comb += self.o.of.round_bit.eq(a1.m[ms-2])
            comb += self.o.of.sticky.eq(a1.m[:ms-2].bool())
            comb += self.o.of.m0.eq(a1.m[ms])  # bit of a1

            # XXX TODO: this is basically duplicating FPRoundMod. hmmm...
            print("alen", a1.e_start, z1.fp.N126, N126)
            print("m1", self.o.z.rmw, a1.m[-self.o.z.rmw-1:])
            mo = Signal(self.o.z.m_width-1)
            comb += mo.eq(a1.m[ms:me])
            with m.If(self.o.of.roundz):
                with m.If((~mo == 0)):  # all 1s
                    comb += self.o.z.create(a1.s, a1.e+1, mo+1)
                with m.Else():
                    comb += self.o.z.create(a1.s, a1.e, mo+1)
            with m.Else():
                comb += self.o.z.create(a1.s, a1.e, a1.m[-self.o.z.rmw-1:])
            comb += self.o.out_do_z.eq(1)

        # copy the context (muxid, operator)
        comb += self.o.oz.eq(self.o.z.v)
        comb += self.o.ctx.eq(self.i.ctx)

        return m


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


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


class SignedOp:
    def __init__(self):
        self.signed = Signal(reset_less=True)

    def eq(self, i):
        return [self.signed.eq(i)]


class FPCVTFloatToIntMod(Elaboratable):
    """ integer to FP conversion: copes with 16/32/64 fp to 16/32/64 int/uint

        self.ctx.i.op & 0x1 == 0x1 : SIGNED int
        self.ctx.i.op & 0x1 == 0x0 : UNSIGNED int

        Note: this is a single-stage conversion that goes direct to FPPackData
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

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        a1 = FPNumBaseRecord(self.in_pspec.width, False)
        print("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.d.comb += a1.v.eq(self.i.a)
        z1 = self.o.z
        mz = len(z1)
        print("z1", mz)

        me = a1.rmw
        ms = mz - me
        print("ms-me", ms, me)

        espec = (a1.e_width, True)
        ediff_intwid = Signal(espec, reset_less=True)

        # conversion can mostly be done manually...
        #m.d.comb += self.o.z.s.eq(a1.s)
        #m.d.comb += self.o.z.e.eq(a1.e)
        #m.d.comb += self.o.z.m[ms:].eq(a1.m)
        #m.d.comb += self.o.z.create(a1.s, a1.e, self.o.z.m) # ... here

        signed = Signal(reset_less=True)
        m.d.comb += signed.eq(self.i.ctx.op[0])

        # special cases
        with m.If(a1.exp_n127):
            m.d.comb += self.o.z.eq(0)

        # signed, exp too big
        with m.Elif(signed & (a1.e > Const(mz-1, espec))):
            with m.If(a1.s): # negative FP, so negative overrun
                m.d.comb += self.o.z.eq(-(1<<(mz-1)))
            with m.Else(): # positive FP, so positive overrun
                m.d.comb += self.o.z.eq((1<<(mz-1)-1))

        # unsigned, exp too big
        with m.Elif((~signed) & (a1.e > Const(mz, espec))):
            with m.If(a1.s): # negative FP, so negative overrun (zero)
                m.d.comb += self.o.z.eq(0)
            with m.Else(): # positive FP, so positive overrun (max INT)
                m.d.comb += self.o.z.eq((1<<(mz)-1))

        # ok exp should be in range: shift and round it
        with m.Else():
            mantissa = Signal(mz, reset_less=True)
            l = [0] * ms + [1] + [a1.m]
            m.d.comb += mantissa.eq(Cat(*l))
            m.d.comb += self.o.z.eq(mantissa)

            # shift
            msr = FPEXPHigh(mz+3, espec[0])
            m.submodules.norm_exp = msr
            m.d.comb += [msr.m_in[3:].eq(mantissa),
                         msr.e_in.eq(a1.e),
                         msr.ediff.eq(Mux(signed, mz-1, mz))
                        ]

            of = Overflow()
            m.d.comb += of.guard.eq(msr.m_out[2])
            m.d.comb += of.round_bit.eq(msr.m_out[1])
            m.d.comb += of.sticky.eq(msr.m_out[0])
            m.d.comb += of.m0.eq(msr.m_out[3])
            m.d.comb += self.o.z.eq(msr.m_out[3:])

        # copy the context (muxid, operator)
        #m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPCVTIntToFloatMod(Elaboratable):
    """ FP integer conversion: copes with 16/32/64 int to 16/32/64 fp.

        self.ctx.i.op & 0x1 == 0x1 : SIGNED int
        self.ctx.i.op & 0x1 == 0x0 : UNSIGNED int
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
        m.submodules.intconvert = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        print("a1", self.in_pspec.width)
        z1 = self.o.z
        print("z1", z1.width, z1.rmw, z1.e_width, z1.e_start, z1.e_end)

        me = self.in_pspec.width
        mz = self.o.z.rmw
        ms = mz - me
        print("ms-me", ms, me, mz)

        # 3 extra bits for guard/round/sticky
        msb = FPMSBHigh(me+3, z1.e_width)
        m.submodules.norm_msb = msb

        # signed or unsigned, use operator context
        signed = Signal(reset_less=True)
        m.d.comb += signed.eq(self.i.ctx.op[0])

        # copy of mantissa (one less bit if signed)
        mantissa = Signal(me, reset_less=True)

        # detect signed/unsigned.  key case: -ve numbers need inversion
        # to +ve because the FP sign says if it's -ve or not.
        with m.If(signed):
            m.d.comb += z1.s.eq(self.i.a[-1])      # sign in top bit of a
            with m.If(z1.s):
                m.d.comb += mantissa.eq(-self.i.a) # invert input if sign -ve
            with m.Else():
                m.d.comb += mantissa.eq(self.i.a)  # leave as-is
        with m.Else():
            m.d.comb += mantissa.eq(self.i.a)      # unsigned, use full a
            m.d.comb += z1.s.eq(0)

        # set input from full INT
        m.d.comb += msb.m_in.eq(Cat(0, 0, 0, mantissa)) # g/r/s + input
        m.d.comb += msb.e_in.eq(me)                     # exp = int width

        # to do with FP16... not yet resolved why
        alternative = ms < 0

        if alternative:
            m.d.comb += z1.e.eq(msb.e_out-1)
            mmsb = msb.m_out[-mz-1:]
            if mz == 16:
                # larger int to smaller FP (uint32/64 -> fp16 most likely)
                m.d.comb += z1.m[ms-1:].eq(mmsb)
            else: # 32? XXX weirdness...
                m.d.comb += z1.m.eq(mmsb)
        else:
            # smaller int to larger FP
            m.d.comb += z1.e.eq(msb.e_out)
            m.d.comb += z1.m[ms:].eq(msb.m_out[3:])
        m.d.comb += z1.create(z1.s, z1.e, z1.m) # ... here

        # note: post-normalisation actually appears to be capable of
        # detecting overflow to infinity (FPPackMod).  so it's ok to
        # drop the bits into the mantissa (with a fixed exponent),
        # do some rounding (which might result in exceeding the
        # range of the target FP by re-increasing the exponent),
        # and basically *not* have to do any kind of range-checking
        # here: just set up guard/round/sticky, drop the INT into the
        # mantissa, and away we go.  XXX TODO: see if FPNormaliseMod
        # is even necessary.  it probably isn't

        # initialise rounding (but only activate if needed)
        if alternative:
            # larger int to smaller FP (uint32/64 -> fp16 most likely)
            m.d.comb += self.o.of.guard.eq(msb.m_out[-mz-2])
            m.d.comb += self.o.of.round_bit.eq(msb.m_out[-mz-3])
            m.d.comb += self.o.of.sticky.eq(msb.m_out[:-mz-3].bool())
            m.d.comb += self.o.of.m0.eq(msb.m_out[-mz-1])
        else:
            # smaller int to larger FP
            m.d.comb += self.o.of.guard.eq(msb.m_out[2])
            m.d.comb += self.o.of.round_bit.eq(msb.m_out[1])
            m.d.comb += self.o.of.sticky.eq(msb.m_out[:1].bool())
            m.d.comb += self.o.of.m0.eq(msb.m_out[3])

        # special cases active by default
        m.d.comb += self.o.out_do_z.eq(1)

        # detect zero
        with m.If(~self.i.a.bool()):
            m.d.comb += self.o.z.zero(0)
        with m.Else():
            m.d.comb += self.o.out_do_z.eq(0) # activate normalisation

        # copy the context (muxid, operator)
        m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPCVTUpConvertMod(Elaboratable):
    """ FP up-conversion (lower to higher bitwidth)
    """
    def __init__(self, in_pspec, out_pspec):
        self.in_pspec = in_pspec
        self.out_pspec = out_pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.in_pspec)

    def ospec(self):
        return FPAddStage1Data(self.out_pspec, e_extra=False)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.upconvert = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        a1 = FPNumBaseRecord(self.in_pspec.width, False)
        print("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.d.comb += a1.v.eq(self.i.a)
        z1 = self.o.z
        print("z1", z1.width, z1.rmw, z1.e_width, z1.e_start, z1.e_end)

        me = a1.rmw
        ms = self.o.z.rmw - a1.rmw
        print("ms-me", ms, me, self.o.z.rmw, a1.rmw)

        # conversion can mostly be done manually...
        m.d.comb += self.o.z.s.eq(a1.s)
        m.d.comb += self.o.z.e.eq(a1.e)
        m.d.comb += self.o.z.m[ms:].eq(a1.m)
        m.d.comb += self.o.z.create(a1.s, a1.e, self.o.z.m) # ... here

        # initialise rounding to all zeros (deactivate)
        m.d.comb += self.o.of.guard.eq(0)
        m.d.comb += self.o.of.round_bit.eq(0)
        m.d.comb += self.o.of.sticky.eq(0)
        m.d.comb += self.o.of.m0.eq(a1.m[0])

        # most special cases active (except tiny-number normalisation, below)
        m.d.comb += self.o.out_do_z.eq(1)

        # detect NaN/Inf first
        with m.If(a1.exp_128):
            with m.If(~a1.m_zero):
                m.d.comb += self.o.z.nan(0) # RISC-V wants normalised NaN
            with m.Else():
                m.d.comb += self.o.z.inf(a1.s) # RISC-V wants signed INF
        with m.Else():
            with m.If(a1.exp_n127):
                with m.If(~a1.m_zero):
                    m.d.comb += self.o.z.m[ms:].eq(Cat(0, a1.m))
                    m.d.comb += self.o.out_do_z.eq(0) # activate normalisation
                with m.Else():
                    # RISC-V zero needs actual zero
                    m.d.comb += self.o.z.zero(a1.s)

        # copy the context (muxid, operator)
        m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


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
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        a1 = FPNumBaseRecord(self.in_pspec.width, False)
        print("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.d.comb += a1.v.eq(self.i.a)
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
        m.d.comb += exp_sub_n126.eq(a1.e - N126)
        m.d.comb += exp_gt127.eq(a1.e > P127)

        # if a zero, return zero (signed)
        with m.If(a1.exp_n127):
            m.d.comb += self.o.z.zero(a1.s)
            m.d.comb += self.o.out_do_z.eq(1)

        # if a range outside z's min range (-126)
        with m.Elif(exp_sub_n126 < 0):
            m.d.comb += self.o.of.guard.eq(a1.m[ms-1])
            m.d.comb += self.o.of.round_bit.eq(a1.m[ms-2])
            m.d.comb += self.o.of.sticky.eq(a1.m[:ms-2].bool())
            m.d.comb += self.o.of.m0.eq(a1.m[ms])  # bit of a1

            m.d.comb += self.o.z.s.eq(a1.s)
            m.d.comb += self.o.z.e.eq(a1.e)
            m.d.comb += self.o.z.m.eq(a1.m[-self.o.z.rmw-1:])
            m.d.comb += self.o.z.m[-1].eq(1)

        # if a is inf return inf
        with m.Elif(a1.is_inf):
            m.d.comb += self.o.z.inf(a1.s)
            m.d.comb += self.o.out_do_z.eq(1)

        # if a is NaN return NaN
        with m.Elif(a1.is_nan):
            m.d.comb += self.o.z.nan(0)
            m.d.comb += self.o.out_do_z.eq(1)

        # if a mantissa greater than 127, return inf
        with m.Elif(exp_gt127):
            print("inf", self.o.z.inf(a1.s))
            m.d.comb += self.o.z.inf(a1.s)
            m.d.comb += self.o.out_do_z.eq(1)

        # ok after all that, anything else should fit fine (whew)
        with m.Else():
            m.d.comb += self.o.of.guard.eq(a1.m[ms-1])
            m.d.comb += self.o.of.round_bit.eq(a1.m[ms-2])
            m.d.comb += self.o.of.sticky.eq(a1.m[:ms-2].bool())
            m.d.comb += self.o.of.m0.eq(a1.m[ms])  # bit of a1

            # XXX TODO: this is basically duplicating FPRoundMod. hmmm...
            print("alen", a1.e_start, z1.fp.N126, N126)
            print("m1", self.o.z.rmw, a1.m[-self.o.z.rmw-1:])
            mo = Signal(self.o.z.m_width-1)
            m.d.comb += mo.eq(a1.m[ms:me])
            with m.If(self.o.of.roundz):
                with m.If((~mo == 0)):  # all 1s
                    m.d.comb += self.o.z.create(a1.s, a1.e+1, mo+1)
                with m.Else():
                    m.d.comb += self.o.z.create(a1.s, a1.e, mo+1)
            with m.Else():
                m.d.comb += self.o.z.create(a1.s, a1.e, a1.m[-self.o.z.rmw-1:])
            m.d.comb += self.o.out_do_z.eq(1)

        # copy the context (muxid, operator)
        m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

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


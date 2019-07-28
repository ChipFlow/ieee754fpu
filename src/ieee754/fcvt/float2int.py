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
        comb = m.d.comb

        # set up FP Num decoder
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        a1 = FPNumBaseRecord(self.in_pspec.width, False)
        print("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        comb += a1.v.eq(self.i.a)
        z1 = self.o.z
        mz = len(z1)
        print("z1", mz)

        me = a1.rmw
        ms = mz - me
        print("ms-me", ms, me)

        espec = (a1.e_width, True)

        signed = Signal(reset_less=True)
        comb += signed.eq(self.i.ctx.op[0])

        # special cases
        with m.If(a1.is_nan):
            with m.If(signed):
                comb += self.o.z.eq((1<<(mz-1))-1) # signed NaN overflow
            with m.Else():
                comb += self.o.z.eq((1<<mz)-1) # NaN overflow

        # zero exponent: definitely out of range of INT.  zero...
        with m.Elif(a1.exp_n127):
            comb += self.o.z.eq(0)

        # unsigned, -ve, return 0
        with m.Elif((~signed) & a1.s):
            comb += self.o.z.eq(0)

        # signed, exp too big
        with m.Elif(signed & (a1.e >= Const(mz-1, espec))):
            with m.If(a1.s): # negative FP, so negative overrun
                comb += self.o.z.eq(-(1<<(mz-1)))
            with m.Else(): # positive FP, so positive overrun
                comb += self.o.z.eq((1<<(mz-1))-1)

        # unsigned, exp too big
        with m.Elif((~signed) & (a1.e >= Const(mz, espec))):
            with m.If(a1.s): # negative FP, so negative overrun (zero)
                comb += self.o.z.eq(0)
            with m.Else(): # positive FP, so positive overrun (max INT)
                comb += self.o.z.eq((1<<(mz))-1)

        # ok exp should be in range: shift and round it
        with m.Else():
            mlen = max(a1.m_width, mz) + 5
            mantissa = Signal(mlen, reset_less=True)
            l = [0] * 2 + [a1.m[:-1]] + [1]
            comb += mantissa[-a1.m_width-3:].eq(Cat(*l))
            comb += self.o.z.eq(mantissa)

            # shift
            msr = FPEXPHigh(mlen, espec[0])
            m.submodules.norm_exp = msr
            comb += [msr.m_in.eq(mantissa),
                         msr.e_in.eq(a1.e),
                         msr.ediff.eq(Mux(signed, mz, mz)-a1.e)
                        ]

            of = Overflow()
            comb += of.guard.eq(msr.m_out[2])
            comb += of.round_bit.eq(msr.m_out[1])
            comb += of.sticky.eq(msr.m_out[0])
            comb += of.m0.eq(msr.m_out[3])

            # XXX TODO: check if this overflows the mantissa
            mround = Signal(mlen, reset_less=True)
            with m.If(of.roundz):
                comb += mround.eq(msr.m_out[3:]+1)
            with m.Else():
                comb += mround.eq(msr.m_out[3:])

            # check sign
            with m.If(signed & a1.s):
                comb += self.o.z.eq(-mround) # inverted
            with m.Else():
                comb += self.o.z.eq(mround)

        # copy the context (muxid, operator)
        #comb += self.o.oz.eq(self.o.z.v)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

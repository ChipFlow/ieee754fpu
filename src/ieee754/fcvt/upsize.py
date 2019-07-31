# IEEE754 Floating Point Conversion
# Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>


import sys
import functools

from nmigen import Module, Signal, Cat
from nmigen.cli import main, verilog

from nmutil.pipemodbase import PipeModBase
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.postcalc import FPPostCalcData
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord


class FPCVTUpConvertMod(PipeModBase):
    """ FP up-conversion (lower to higher bitwidth)
    """
    def __init__(self, in_pspec, out_pspec):
        self.in_pspec = in_pspec
        self.out_pspec = out_pspec
        super().__init__(in_pspec, "upconvert")

    def ispec(self):
        return FPBaseData(self.in_pspec)

    def ospec(self):
        return FPPostCalcData(self.out_pspec, e_extra=False)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        print("in_width out", self.in_pspec.width, self.out_pspec.width)

        # this is quite straightforward as there is plenty of space in
        # the larger format to fit the smaller-bit-width exponent+mantissa
        # the special cases are detecting Inf and NaN and de-normalised
        # "tiny" numbers.  the "subnormal" numbers (ones at the limit of
        # the smaller exponent range) need to be normalised to fit into
        # the (larger) exponent.

        a1 = FPNumBaseRecord(self.in_pspec.width, False)
        print("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        comb += a1.v.eq(self.i.a)

        z1 = self.o.z
        print("z1", z1.width, z1.rmw, z1.e_width, z1.e_start, z1.e_end)

        me = a1.rmw
        ms = self.o.z.rmw - a1.rmw
        print("ms-me", ms, me, self.o.z.rmw, a1.rmw)

        # conversion can mostly be done manually...
        comb += self.o.z.s.eq(a1.s)
        comb += self.o.z.e.eq(a1.e)
        comb += self.o.z.m[ms:].eq(a1.m)
        comb += self.o.z.create(a1.s, a1.e, self.o.z.m) # ... here


        # special cases active (except tiny-number normalisation, below)
        comb += self.o.out_do_z.eq(1)

        # detect NaN/Inf first
        with m.If(a1.exp_128):
            with m.If(~a1.m_zero):
                comb += self.o.z.nan(0) # RISC-V wants normalised NaN
            with m.Else():
                comb += self.o.z.inf(a1.s) # RISC-V wants signed INF
        with m.Else():
            # now check zero (or subnormal)
            with m.If(a1.exp_n127): # subnormal number detected (or zero)
                with m.If(~a1.m_zero):
                    # non-zero mantissa: needs normalisation
                    comb += self.o.z.m[ms:].eq(Cat(0, a1.m))
                    comb += self.o.of.m0.eq(a1.m[0]) # Overflow needs LSB
                    comb += self.o.out_do_z.eq(0) # activate normalisation
                with m.Else():
                    # RISC-V zero needs actual zero
                    comb += self.o.z.zero(a1.s)
            # anything else, amazingly, is fine as-is.

        # copy the context (muxid, operator)
        comb += self.o.oz.eq(self.o.z.v)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

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
        ms = self.o.z.rmw - a1.rmw
        print("ms-me", ms, me, self.o.z.rmw, a1.rmw)

        # conversion can mostly be done manually...
        comb += self.o.z.s.eq(a1.s)
        comb += self.o.z.e.eq(a1.e)
        comb += self.o.z.m[ms:].eq(a1.m)
        comb += self.o.z.create(a1.s, a1.e, self.o.z.m) # ... here

        # initialise rounding to all zeros (deactivate)
        comb += self.o.of.guard.eq(0)
        comb += self.o.of.round_bit.eq(0)
        comb += self.o.of.sticky.eq(0)
        comb += self.o.of.m0.eq(a1.m[0])

        # most special cases active (except tiny-number normalisation, below)
        comb += self.o.out_do_z.eq(1)

        # detect NaN/Inf first
        with m.If(a1.exp_128):
            with m.If(~a1.m_zero):
                comb += self.o.z.nan(0) # RISC-V wants normalised NaN
            with m.Else():
                comb += self.o.z.inf(a1.s) # RISC-V wants signed INF
        with m.Else():
            with m.If(a1.exp_n127):
                with m.If(~a1.m_zero):
                    comb += self.o.z.m[ms:].eq(Cat(0, a1.m))
                    comb += self.o.out_do_z.eq(0) # activate normalisation
                with m.Else():
                    # RISC-V zero needs actual zero
                    comb += self.o.z.zero(a1.s)

        # copy the context (muxid, operator)
        comb += self.o.oz.eq(self.o.z.v)
        comb += self.o.ctx.eq(self.i.ctx)

        return m

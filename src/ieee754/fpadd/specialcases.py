# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Const
from nmigen.cli import main, verilog
from math import log

from nmutil.pipemodbase import PipeModBase, PipeModBaseChain
from ieee754.fpcommon.fpbase import FPNumDecode

from ieee754.fpcommon.fpbase import FPNumBaseRecord
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.denorm import (FPSCData, FPAddDeNormMod)


class FPAddSpecialCasesMod(PipeModBase):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, pspec):
        super().__init__(pspec, "specialcases")

    def ispec(self):
        return FPBaseData(self.pspec)

    def ospec(self):
        return FPSCData(self.pspec, True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # decode: XXX really should move to separate stage
        width = self.pspec.width
        a1 = FPNumBaseRecord(width)
        b1 = FPNumBaseRecord(width)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        comb += [a1.v.eq(self.i.a),
                     b1.v.eq(self.i.b),
                     self.o.a.eq(a1),
                     self.o.b.eq(b1)
                    ]

        # temporaries used below
        s_nomatch = Signal(reset_less=True)
        m_match = Signal(reset_less=True)
        e_match = Signal(reset_less=True)
        aeqmb = Signal(reset_less=True)
        abz = Signal(reset_less=True)
        absa = Signal(reset_less=True)
        abnan = Signal(reset_less=True)
        bexp128s = Signal(reset_less=True)

        comb += s_nomatch.eq(a1.s != b1.s)
        comb += m_match.eq(a1.m == b1.m)
        comb += e_match.eq(a1.e == b1.e)
        comb += aeqmb.eq(s_nomatch & m_match & e_match)
        comb += abz.eq(a1.is_zero & b1.is_zero)
        comb += absa.eq(a1.s & b1.s)
        comb += abnan.eq(a1.is_nan | b1.is_nan)
        comb += bexp128s.eq(b1.exp_128 & s_nomatch)

        # prepare inf/zero/nans
        z_zero = FPNumBaseRecord(width, False, name="z_zero")
        z_nan = FPNumBaseRecord(width, False, name="z_nan")
        z_infa = FPNumBaseRecord(width, False, name="z_infa")
        z_infb = FPNumBaseRecord(width, False, name="z_infb")
        comb += z_zero.zero(0)
        comb += z_nan.nan(0)
        comb += z_infa.inf(a1.s)
        comb += z_infb.inf(b1.s)

        # default bypass
        comb += self.o.out_do_z.eq(1)

        # if a is NaN or b is NaN return NaN
        with m.If(abnan):
            comb += self.o.oz.eq(z_nan.v)

        # if a is inf return inf (or NaN)
        with m.Elif(a1.is_inf):
            comb += self.o.oz.eq(z_infa.v)
            # if a is inf and signs don't match return NaN
            with m.If(bexp128s):
                comb += self.o.oz.eq(z_nan.v)

        # if b is inf return inf
        with m.Elif(b1.is_inf):
            comb += self.o.oz.eq(z_infb.v)

        # if a is zero and b zero return signed-a/b
        with m.Elif(abz):
            comb += self.o.oz.eq(self.i.b)
            comb += self.o.oz[-1].eq(absa)

        # if a is zero return b
        with m.Elif(a1.is_zero):
            comb += self.o.oz.eq(b1.v)

        # if b is zero return a
        with m.Elif(b1.is_zero):
            comb += self.o.oz.eq(a1.v)

        # if a equal to -b return zero (+ve zero)
        with m.Elif(aeqmb):
            comb += self.o.oz.eq(z_zero.v)

        # Denormalised Number checks next, so pass a/b data through
        with m.Else():
            comb += self.o.out_do_z.eq(0)

        comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPAddSpecialCasesDeNorm(PipeModBaseChain):
    """ special cases chain
    """

    def get_chain(self):
        """ links module to inputs and outputs
        """
        smod = FPAddSpecialCasesMod(self.pspec)
        dmod = FPAddDeNormMod(self.pspec, True)

        return [smod, dmod]

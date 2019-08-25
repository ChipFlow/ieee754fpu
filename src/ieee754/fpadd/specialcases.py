# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Const, Mux
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
        absa = Signal(reset_less=True) # a1.s & b1.s
        t_aeqmb = Signal(reset_less=True)
        t_a1inf = Signal(reset_less=True)
        t_b1inf = Signal(reset_less=True)
        t_a1zero = Signal(reset_less=True)
        t_b1zero = Signal(reset_less=True)
        t_abz = Signal(reset_less=True)
        t_abnan = Signal(reset_less=True)
        bexp128s = Signal(reset_less=True)
        t_special = Signal(reset_less=True)

        comb += s_nomatch.eq(a1.s != b1.s)
        comb += m_match.eq(a1.m == b1.m)
        comb += e_match.eq(a1.e == b1.e)

        # logic-chain (matches comments, below) gives an if-elif-elif-elif...
        comb += t_abnan.eq(a1.is_nan | b1.is_nan)
        comb += t_a1inf.eq(a1.is_inf)
        comb += t_b1inf.eq(b1.is_inf)
        comb += t_abz.eq(a1.is_zero & b1.is_zero)
        comb += t_a1zero.eq(a1.is_zero)
        comb += t_b1zero.eq(b1.is_zero)
        comb += t_aeqmb.eq(s_nomatch & m_match & e_match)
        comb += t_special.eq(Cat(t_aeqmb, t_b1zero, t_a1zero, t_abz,
                                     t_b1inf, t_a1inf, t_abnan).bool())

        comb += absa.eq(a1.s & b1.s)
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

        # any special-cases it's a "special".
        comb += self.o.out_do_z.eq(t_special)

        # this is the logic-decision-making for special-cases:
        # if a is NaN or b is NaN return NaN
        # elif a is inf return inf (or NaN)
        #   if a is inf and signs don't match return NaN
        #   else return inf(a)
        # elif b is inf return inf(b)
        # elif a is zero and b zero return signed-a/b
        # elif a is zero return b
        # elif b is zero return a
        # elif a equal to -b return zero (+ve zero)

        # XXX *sigh* there are better ways to do this...
        # one of them: use a priority-picker!
        # in reverse-order, accumulate Muxing

        oz = 0
        oz = Mux(t_aeqmb, z_zero.v, oz)
        oz = Mux(t_b1zero, a1.v, oz)
        oz = Mux(t_a1zero, b1.v, oz)
        oz = Mux(t_abz, Cat(self.i.b[:-1], absa), oz)
        oz = Mux(t_b1inf, z_infb.v, oz)
        oz = Mux(t_a1inf, Mux(bexp128s, z_nan.v, z_infa.v), oz)
        oz = Mux(t_abnan, z_nan.v, oz)

        comb += self.o.oz.eq(oz)

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

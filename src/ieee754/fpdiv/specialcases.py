""" IEEE Floating Point Divider

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2019 Jacob Lifshay

Relevant bugreports:
* http://bugs.libre-riscv.org/show_bug.cgi?id=99
* http://bugs.libre-riscv.org/show_bug.cgi?id=43
* http://bugs.libre-riscv.org/show_bug.cgi?id=44
"""

from nmigen import Module, Signal, Cat, Mux
from nmigen.cli import main, verilog
from math import log

from nmutil.pipemodbase import PipeModBase, PipeModBaseChain
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.denorm import (FPSCData, FPAddDeNormMod)
from ieee754.fpmul.align import FPAlignModSingle
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation as DP


class FPDIVSpecialCasesMod(PipeModBase):
    """ special cases: NaNs, infs, zeros, denormalised
        see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, pspec):
        super().__init__(pspec, "specialcases")

    def ispec(self):
        return FPBaseData(self.pspec)

    def ospec(self):
        return FPSCData(self.pspec, False)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # decode: XXX really should move to separate stage
        width = self.pspec.width
        a1 = FPNumBaseRecord(width, False, name="a1")
        b1 = FPNumBaseRecord(width, False, name="b1")
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        comb += [a1.v.eq(self.i.a),
                     b1.v.eq(self.i.b),
                     self.o.a.eq(a1),
                     self.o.b.eq(b1)
                     ]

        # temporaries (used below)
        sabx = Signal(reset_less=True)   # sign a xor b (sabx, get it?)
        t_abnan = Signal(reset_less=True)
        t_abinf = Signal(reset_less=True)
        t_a1inf = Signal(reset_less=True)
        t_b1inf = Signal(reset_less=True)
        t_a1zero = Signal(reset_less=True)
        t_b1zero = Signal(reset_less=True)
        t_abz = Signal(reset_less=True)
        t_special_div = Signal(reset_less=True)
        t_special_sqrt = Signal(reset_less=True)
        t_special_rsqrt = Signal(reset_less=True)

        comb += sabx.eq(a1.s ^ b1.s)
        comb += t_abnan.eq(a1.is_nan | b1.is_nan)
        comb += t_abinf.eq(a1.is_inf & b1.is_inf)
        comb += t_a1inf.eq(a1.is_inf)
        comb += t_b1inf.eq(b1.is_inf)
        comb += t_abz.eq(a1.is_zero & b1.is_zero)
        comb += t_a1zero.eq(a1.is_zero)
        comb += t_b1zero.eq(b1.is_zero)

        # prepare inf/zero/nans
        z_zero = FPNumBaseRecord(width, False, name="z_zero")
        z_zeroab = FPNumBaseRecord(width, False, name="z_zeroab")
        z_nan = FPNumBaseRecord(width, False, name="z_nan")
        z_infa = FPNumBaseRecord(width, False, name="z_infa")
        z_infb = FPNumBaseRecord(width, False, name="z_infb")
        z_infab = FPNumBaseRecord(width, False, name="z_infab")
        comb += z_zero.zero(0)
        comb += z_zeroab.zero(sabx)
        comb += z_nan.nan(0)
        comb += z_infa.inf(a1.s)
        comb += z_infb.inf(b1.s)
        comb += z_infab.inf(sabx)

        comb += t_special_div.eq(Cat(t_b1zero, t_a1zero, t_b1inf, t_a1inf,
                                     t_abinf, t_abnan).bool())

        # select one of 3 different sets of specialcases (DIV, SQRT, RSQRT)
        with m.Switch(self.i.ctx.op):

            ########## DIV ############
            with m.Case(int(DP.UDivRem)):

                # any special cases?
                comb += self.o.out_do_z.eq(t_special_div)

                # if a is NaN or b is NaN return NaN
                # if a is inf and b is Inf return NaN
                # if a is inf return inf
                # if b is inf return zero
                # if a is zero return zero (or NaN if b is zero)
                    # b is zero return NaN
                # if b is zero return Inf

                # sigh inverse order on the above, Mux-cascade
                oz = 0
                oz = Mux(t_b1zero, z_infab.v, oz)
                oz = Mux(t_a1zero, Mux(t_b1zero, z_nan.v, z_zeroab.v), oz)
                oz = Mux(t_b1inf, z_zeroab.v, oz)
                oz = Mux(t_a1inf, z_infab.v, oz)
                oz = Mux(t_abinf, z_nan.v, oz)
                oz = Mux(t_abnan, z_nan.v, oz)

                comb += self.o.oz.eq(oz)

            ########## SQRT ############
            with m.Case(int(DP.SqrtRem)):

                # if a is zero return zero
                with m.If(a1.is_zero):
                    comb += self.o.z.zero(a1.s)

                # -ve number is NaN
                with m.Elif(a1.s):
                    comb += self.o.z.nan(0)

                # if a is inf return inf
                with m.Elif(a1.is_inf):
                    comb += self.o.z.inf(sabx)

                # if a is NaN return NaN
                with m.Elif(a1.is_nan):
                    comb += self.o.z.nan(0)

                # Denormalised Number checks next, so pass a/b data through
                with m.Else():
                    comb += self.o.out_do_z.eq(0)

                comb += self.o.oz.eq(self.o.z.v)

            ########## RSQRT ############
            with m.Case(int(DP.RSqrtRem)):

                # if a is NaN return canonical NaN
                with m.If(a1.is_nan):
                    comb += self.o.z.nan(0)

                # if a is +/- zero return +/- INF
                with m.Elif(a1.is_zero):
                    # this includes the "weird" case 1/sqrt(-0) == -Inf
                    comb += self.o.z.inf(a1.s)

                # -ve number is canonical NaN
                with m.Elif(a1.s):
                    comb += self.o.z.nan(0)

                # if a is inf return zero (-ve already excluded, above)
                with m.Elif(a1.is_inf):
                    comb += self.o.z.zero(0)

                # Denormalised Number checks next, so pass a/b data through
                with m.Else():
                    comb += self.o.out_do_z.eq(0)

                comb += self.o.oz.eq(self.o.z.v)

        # pass through context
        comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPDIVSpecialCasesDeNorm(PipeModBaseChain):
    """ special cases: NaNs, infs, zeros, denormalised
    """

    def get_chain(self):
        """ links module to inputs and outputs
        """
        smod = FPDIVSpecialCasesMod(self.pspec)
        dmod = FPAddDeNormMod(self.pspec, False)
        amod = FPAlignModSingle(self.pspec, False)

        return [smod, dmod, amod]

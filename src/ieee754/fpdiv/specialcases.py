""" IEEE Floating Point Divider

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2019 Jacob Lifshay

Relevant bugreports:
* http://bugs.libre-riscv.org/show_bug.cgi?id=99
* http://bugs.libre-riscv.org/show_bug.cgi?id=43
* http://bugs.libre-riscv.org/show_bug.cgi?id=44
"""

from nmigen import Module, Signal
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.modbase import FPModBase, FPModBaseChain
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import (FPSCData, FPAddDeNormMod)
from ieee754.fpmul.align import FPAlignModSingle
from ieee754.div_rem_sqrt_rsqrt.core import DivPipeCoreOperation as DP


class FPDIVSpecialCasesMod(FPModBase):
    """ special cases: NaNs, infs, zeros, denormalised
        see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, pspec):
        super().__init__(pspec, "specialcases")

    def ispec(self):
        return FPADDBaseData(self.pspec)

    def ospec(self):
        return FPSCData(self.pspec, False)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # decode: XXX really should move to separate stage
        a1 = FPNumBaseRecord(self.pspec.width, False, name="a1")
        b1 = FPNumBaseRecord(self.pspec.width, False, name="b1")
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        comb += [a1.v.eq(self.i.a),
                     b1.v.eq(self.i.b),
                     self.o.a.eq(a1),
                     self.o.b.eq(b1)
                     ]

        # temporaries (used below)
        sabx = Signal(reset_less=True)   # sign a xor b (sabx, get it?)
        abnan = Signal(reset_less=True)
        abinf = Signal(reset_less=True)

        comb += sabx.eq(a1.s ^ b1.s)
        comb += abnan.eq(a1.is_nan | b1.is_nan)
        comb += abinf.eq(a1.is_inf & b1.is_inf)

        # default (overridden if needed)
        comb += self.o.out_do_z.eq(1)

        # select one of 3 different sets of specialcases (DIV, SQRT, RSQRT)
        with m.Switch(self.i.ctx.op):

            with m.Case(int(DP.UDivRem)): # DIV

                # if a is NaN or b is NaN return NaN
                with m.If(abnan):
                    comb += self.o.z.nan(0)

                # if a is inf and b is Inf return NaN
                with m.Elif(abinf):
                    comb += self.o.z.nan(0)

                # if a is inf return inf
                with m.Elif(a1.is_inf):
                    comb += self.o.z.inf(sabx)

                # if b is inf return zero
                with m.Elif(b1.is_inf):
                    comb += self.o.z.zero(sabx)

                # if a is zero return zero (or NaN if b is zero)
                with m.Elif(a1.is_zero):
                    comb += self.o.z.zero(sabx)
                    # b is zero return NaN
                    with m.If(b1.is_zero):
                        comb += self.o.z.nan(0)

                # if b is zero return Inf
                with m.Elif(b1.is_zero):
                    comb += self.o.z.inf(sabx)

                # Denormalised Number checks next, so pass a/b data through
                with m.Else():
                    comb += self.o.out_do_z.eq(0)

            with m.Case(int(DP.SqrtRem)): # SQRT

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

            with m.Case(int(DP.RSqrtRem)): # RSQRT

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
        comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPDIVSpecialCasesDeNorm(FPModBaseChain):
    """ special cases: NaNs, infs, zeros, denormalised
    """

    def get_chain(self):
        """ links module to inputs and outputs
        """
        smod = FPDIVSpecialCasesMod(self.pspec)
        dmod = FPAddDeNormMod(self.pspec, False)
        amod = FPAlignModSingle(self.pspec, False)

        return [smod, dmod, amod]

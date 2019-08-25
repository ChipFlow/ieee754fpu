"""IEEE754 Floating Point Multiplier

Copyright (C) 2019 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
Copyright (C) 2019 Jake Lifshay

"""

from nmigen import Module, Signal, Cat, Const, Mux
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord

from nmutil.pipemodbase import PipeModBase, PipeModBaseChain
from ieee754.fpcommon.basedata import FPBaseData
from ieee754.fpcommon.denorm import (FPSCData, FPAddDeNormMod)
from ieee754.fpmul.align import FPAlignModSingle


class FPMulSpecialCasesMod(PipeModBase):
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

        # decode a/b
        width = self.pspec.width
        a1 = FPNumBaseRecord(width, False)
        b1 = FPNumBaseRecord(width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        comb += [a1.v.eq(self.i.a),
                     b1.v.eq(self.i.b),
                     self.o.a.eq(a1),
                     self.o.b.eq(b1)
                    ]

        # intermediaries / tests
        t_obz = Signal(reset_less=True)
        t_a1inf = Signal(reset_less=True)
        t_b1inf = Signal(reset_less=True)
        t_abnan = Signal(reset_less=True)
        t_special = Signal(reset_less=True)
        sabx = Signal(reset_less=True)   # sign a xor b (sabx, get it?)

        comb += sabx.eq(a1.s ^ b1.s)
        comb += t_obz.eq(a1.is_zero | b1.is_zero)
        comb += t_a1inf.eq(a1.is_inf)
        comb += t_b1inf.eq(b1.is_inf)
        comb += t_abnan.eq(a1.is_nan | b1.is_nan)
        comb += t_special.eq(Cat(t_obz, t_abnan, t_b1inf, t_a1inf).bool())

        # prepare inf/zero/nans
        z_zero = FPNumBaseRecord(width, False, name="z_zero")
        z_nan = FPNumBaseRecord(width, False, name="z_nan")
        z_inf = FPNumBaseRecord(width, False, name="z_inf")
        comb += z_zero.zero(sabx)
        comb += z_nan.nan(0)
        comb += z_inf.inf(sabx)

        # special case pipeline bypass enabled y/n
        comb += self.o.out_do_z.eq(t_special)

        # if a is NaN or b is NaN return NaN
        # if a is inf return inf (or NaN)
        #   if b is zero return NaN
        # if b is inf return inf (or NaN)
        #   if a is zero return NaN
        # if a is zero or b zero return signed-a/b

        # invert the sequence above to create the Mux tree
        # XXX TODO: use PriorityPicker?
        oz = 0
        oz = Mux(t_obz, z_zero.v, oz)
        oz = Mux(t_b1inf, Mux(a1.is_zero, z_nan.v, z_inf.v), oz)
        oz = Mux(t_a1inf, Mux(b1.is_zero, z_nan.v, z_inf.v), oz)
        oz = Mux(t_abnan, z_nan.v, oz)
        comb += self.o.oz.eq(oz)

        # pass through context
        comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPMulSpecialCasesDeNorm(PipeModBaseChain):
    """ special cases: NaNs, infs, zeros, denormalised
    """

    def get_chain(self):
        """ gets chain of modules
        """
        smod = FPMulSpecialCasesMod(self.pspec)
        dmod = FPAddDeNormMod(self.pspec, False)
        amod = FPAlignModSingle(self.pspec, False)

        return [smod, dmod, amod]


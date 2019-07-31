# IEEE Floating Point Multiplier 

from nmigen import Module, Signal, Cat, Const
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord

from nmutil.pipemodbase import FPModBase, FPModBaseChain
from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import (FPSCData, FPAddDeNormMod)
from ieee754.fpmul.align import FPAlignModSingle


class FPMulSpecialCasesMod(FPModBase):
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

        obz = Signal(reset_less=True)
        comb += obz.eq(a1.is_zero | b1.is_zero)

        sabx = Signal(reset_less=True)   # sign a xor b (sabx, get it?)
        comb += sabx.eq(a1.s ^ b1.s)

        abnan = Signal(reset_less=True)
        comb += abnan.eq(a1.is_nan | b1.is_nan)

        # initialise and override if needed
        comb += self.o.out_do_z.eq(1)

        # if a is NaN or b is NaN return NaN
        with m.If(abnan):
            comb += self.o.z.nan(0)

        # if a is inf return inf (or NaN)
        with m.Elif(a1.is_inf):
            comb += self.o.z.inf(sabx)
            # b is zero return NaN
            with m.If(b1.is_zero):
                comb += self.o.z.nan(0)

        # if b is inf return inf (or NaN)
        with m.Elif(b1.is_inf):
            comb += self.o.z.inf(sabx)
            # a is zero return NaN
            with m.If(a1.is_zero):
                comb += self.o.z.nan(0)

        # if a is zero or b zero return signed-a/b
        with m.Elif(obz):
            comb += self.o.z.zero(sabx)

        # Denormalised Number checks next, so pass a/b data through
        with m.Else():
            comb += self.o.out_do_z.eq(0)

        comb += self.o.oz.eq(self.o.z.v)
        comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPMulSpecialCasesDeNorm(FPModBaseChain):
    """ special cases: NaNs, infs, zeros, denormalised
    """

    def get_chain(self):
        """ gets chain of modules
        """
        smod = FPMulSpecialCasesMod(self.pspec)
        dmod = FPAddDeNormMod(self.pspec, False)
        amod = FPAlignModSingle(self.pspec, False)

        return [smod, dmod, amod]


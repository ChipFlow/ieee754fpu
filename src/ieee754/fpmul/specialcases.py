# IEEE Floating Point Multiplier 

from nmigen import Module, Signal, Cat, Const, Elaboratable
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from nmutil.singlepipe import StageChain

from ieee754.pipeline import DynamicPipe
from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import (FPSCData, FPAddDeNormMod)
from ieee754.fpmul.align import FPAlignModSingle


class FPMulSpecialCasesMod(Elaboratable):
    """ special cases: NaNs, infs, zeros, denormalised
        see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, pspec):
        self.pspec = pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.pspec)

    def ospec(self):
        return FPSCData(self.pspec, False)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.specialcases = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        #m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        width = self.pspec.width
        a1 = FPNumBaseRecord(width, False)
        b1 = FPNumBaseRecord(width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        m.d.comb += [a1.v.eq(self.i.a),
                     b1.v.eq(self.i.b),
                     self.o.a.eq(a1),
                     self.o.b.eq(b1)
                    ]

        obz = Signal(reset_less=True)
        m.d.comb += obz.eq(a1.is_zero | b1.is_zero)

        sabx = Signal(reset_less=True)   # sign a xor b (sabx, get it?)
        m.d.comb += sabx.eq(a1.s ^ b1.s)

        abnan = Signal(reset_less=True)
        m.d.comb += abnan.eq(a1.is_nan | b1.is_nan)

        # if a is NaN or b is NaN return NaN
        with m.If(abnan):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.nan(0)

        # if a is inf return inf (or NaN)
        with m.Elif(a1.is_inf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.inf(sabx)
            # b is zero return NaN
            with m.If(b1.is_zero):
                m.d.comb += self.o.z.nan(0)

        # if b is inf return inf (or NaN)
        with m.Elif(b1.is_inf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.inf(sabx)
            # a is zero return NaN
            with m.If(a1.is_zero):
                m.d.comb += self.o.z.nan(0)

        # if a is zero or b zero return signed-a/b
        with m.Elif(obz):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.zero(sabx)

        # Denormalised Number checks next, so pass a/b data through
        with m.Else():
            m.d.comb += self.o.out_do_z.eq(0)

        m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPMulSpecialCasesDeNorm(DynamicPipe):
    """ special cases: NaNs, infs, zeros, denormalised
    """

    def __init__(self, pspec):
        self.pspec = pspec
        super().__init__(pspec)
        self.out = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.pspec)

    def ospec(self):
        return FPSCData(self.pspec, False)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        smod = FPMulSpecialCasesMod(self.pspec)
        dmod = FPAddDeNormMod(self.pspec, False)
        amod = FPAlignModSingle(self.pspec, False)

        chain = StageChain([smod, dmod, amod])
        chain.setup(m, i)

        # only needed for break-out (early-out)
        # self.out_do_z = smod.o.out_do_z

        self.o = amod.o # output is from last .o in the chain

    def process(self, i):
        return self.o


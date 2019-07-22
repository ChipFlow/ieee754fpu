# IEEE Floating Point Multiplier 

from nmigen import Module, Signal, Cat, Const, Elaboratable
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from nmutil.singlepipe import SimpleHandshake, StageChain

from ieee754.fpcommon.fpbase import FPState, FPID
from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.denorm import (FPSCData, FPAddDeNormMod)
from ieee754.fpmul.align import FPAlignModSingle


class FPDIVSpecialCasesMod(Elaboratable):
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
        a1 = FPNumBaseRecord(self.pspec.width, False)
        b1 = FPNumBaseRecord(self.pspec.width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        m.d.comb += [a1.v.eq(self.i.a),
                     b1.v.eq(self.i.b),
                     self.o.a.eq(a1),
                     self.o.b.eq(b1)
                    ]

        sabx = Signal(reset_less=True)   # sign a xor b (sabx, get it?)
        m.d.comb += sabx.eq(a1.s ^ b1.s)

        abnan = Signal(reset_less=True)
        m.d.comb += abnan.eq(a1.is_nan | b1.is_nan)

        abinf = Signal(reset_less=True)
        m.d.comb += abinf.eq(a1.is_inf & b1.is_inf)

        # if a is NaN or b is NaN return NaN
        with m.If(abnan):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.nan(0)

        # if a is inf and b is Inf return NaN
        with m.Elif(abinf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.nan(0)

        # if a is inf return inf
        with m.Elif(a1.is_inf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.inf(sabx)

        # if b is inf return zero
        with m.Elif(b1.is_inf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.zero(sabx)

        # if a is zero return zero (or NaN if b is zero)
        with m.Elif(a1.is_zero):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.zero(sabx)
            # b is zero return NaN
            with m.If(b1.is_zero):
                m.d.comb += self.o.z.nan(0)

        # if b is zero return Inf
        with m.Elif(b1.is_zero):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.inf(sabx)

        # Denormalised Number checks next, so pass a/b data through
        with m.Else():
            m.d.comb += self.o.out_do_z.eq(0)

        m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m


class FPDIVSpecialCases(FPState):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to div.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, pspec):
        FPState.__init__(self, "special_cases")
        self.mod = FPDIVSpecialCasesMod(pspec)
        self.out_z = self.mod.ospec()
        self.out_do_z = Signal(reset_less=True)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i, self.out_do_z)
        m.d.sync += self.out_z.v.eq(self.mod.out_z.v) # only take the output
        m.d.sync += self.out_z.mid.eq(self.mod.o.mid)  # (and mid)

    def action(self, m):
        self.idsync(m)
        with m.If(self.out_do_z):
            m.next = "put_z"
        with m.Else():
            m.next = "denormalise"


class FPDIVSpecialCasesDeNorm(FPState, SimpleHandshake):
    """ special cases: NaNs, infs, zeros, denormalised
    """

    def __init__(self, pspec):
        FPState.__init__(self, "special_cases")
        self.pspec = pspec
        SimpleHandshake.__init__(self, self) # pipe is its own stage
        self.out = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.pspec) # SpecialCases ispec

    def ospec(self):
        return FPSCData(self.pspec, False) # Align ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        smod = FPDIVSpecialCasesMod(self.pspec)
        dmod = FPAddDeNormMod(self.pspec, False)
        amod = FPAlignModSingle(self.pspec, False)

        chain = StageChain([smod, dmod, amod])
        chain.setup(m, i)

        # only needed for break-out (early-out)
        # self.out_do_z = smod.o.out_do_z

        self.o = amod.o

    def process(self, i):
        return self.o

    def action(self, m):
        # for break-out (early-out)
        #with m.If(self.out_do_z):
        #    m.next = "put_z"
        #with m.Else():
            m.d.sync += self.out.eq(self.process(None))
            m.next = "align"



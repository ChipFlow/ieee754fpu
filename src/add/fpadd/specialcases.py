# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Const
from nmigen.cli import main, verilog
from math import log

from fpbase import FPNumIn
from singlepipe import UnbufferedPipeline, StageChain

from fpbase import FPState, FPID
from fpcommon.getop import FPADDBaseData
from fpcommon.denorm import (FPSCData, FPAddDeNormMod)


class FPAddSpecialCasesMod:
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width, id_wid):
        self.width = width
        self.id_wid = id_wid
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.width, self.id_wid)

    def ospec(self):
        return FPSCData(self.width, self.id_wid)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.specialcases = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        m.submodules.sc_out_z = self.o.z

        # decode: XXX really should move to separate stage
        a1 = FPNumIn(None, self.width)
        b1 = FPNumIn(None, self.width)
        m.submodules.sc_decode_a = a1
        m.submodules.sc_decode_b = b1
        m.d.comb += [a1.decode(self.i.a),
                     b1.decode(self.i.b),
                    ]

        s_nomatch = Signal(reset_less=True)
        m.d.comb += s_nomatch.eq(a1.s != b1.s)

        m_match = Signal(reset_less=True)
        m.d.comb += m_match.eq(a1.m == b1.m)

        e_match = Signal(reset_less=True)
        m.d.comb += m_match.eq(a1.e == b1.e)

        aeqmb = Signal(reset_less=True)
        m.d.comb += aeqmb.eq(s_nomatch & m_match & e_match)

        abz = Signal(reset_less=True)
        m.d.comb += abz.eq(a1.is_zero & b1.is_zero)

        abnan = Signal(reset_less=True)
        m.d.comb += abnan.eq(a1.is_nan | b1.is_nan)

        bexp128s = Signal(reset_less=True)
        m.d.comb += bexp128s.eq(b1.exp_128 & s_nomatch)

        # if a is NaN or b is NaN return NaN
        with m.If(abnan):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.nan(0)

        # XXX WEIRDNESS for FP16 non-canonical NaN handling
        # under review

        ## if a is zero and b is NaN return -b
        #with m.If(a.is_zero & (a.s==0) & b.is_nan):
        #    m.d.comb += self.o.out_do_z.eq(1)
        #    m.d.comb += z.create(b.s, b.e, Cat(b.m[3:-2], ~b.m[0]))

        ## if b is zero and a is NaN return -a
        #with m.Elif(b.is_zero & (b.s==0) & a.is_nan):
        #    m.d.comb += self.o.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s, a.e, Cat(a.m[3:-2], ~a.m[0]))

        ## if a is -zero and b is NaN return -b
        #with m.Elif(a.is_zero & (a.s==1) & b.is_nan):
        #    m.d.comb += self.o.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s & b.s, b.e, Cat(b.m[3:-2], 1))

        ## if b is -zero and a is NaN return -a
        #with m.Elif(b.is_zero & (b.s==1) & a.is_nan):
        #    m.d.comb += self.o.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s & b.s, a.e, Cat(a.m[3:-2], 1))

        # if a is inf return inf (or NaN)
        with m.Elif(a1.is_inf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.inf(a1.s)
            # if a is inf and signs don't match return NaN
            with m.If(bexp128s):
                m.d.comb += self.o.z.nan(0)

        # if b is inf return inf
        with m.Elif(b1.is_inf):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.inf(b1.s)

        # if a is zero and b zero return signed-a/b
        with m.Elif(abz):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.create(a1.s & b1.s, b1.e, b1.m[3:-1])

        # if a is zero return b
        with m.Elif(a1.is_zero):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.create(b1.s, b1.e, b1.m[3:-1])

        # if b is zero return a
        with m.Elif(b1.is_zero):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.create(a1.s, a1.e, a1.m[3:-1])

        # if a equal to -b return zero (+ve zero)
        with m.Elif(aeqmb):
            m.d.comb += self.o.out_do_z.eq(1)
            m.d.comb += self.o.z.zero(0)

        # Denormalised Number checks next, so pass a/b data through
        with m.Else():
            m.d.comb += self.o.out_do_z.eq(0)
            m.d.comb += self.o.a.eq(a1)
            m.d.comb += self.o.b.eq(b1)

        m.d.comb += self.o.oz.eq(self.o.z.v)
        m.d.comb += self.o.mid.eq(self.i.mid)

        return m


class FPAddSpecialCases(FPState):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "special_cases")
        self.mod = FPAddSpecialCasesMod(width)
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


class FPAddSpecialCasesDeNorm(FPState, UnbufferedPipeline):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "special_cases")
        self.width = width
        self.id_wid = id_wid
        UnbufferedPipeline.__init__(self, self) # pipe is its own stage
        self.out = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.width, self.id_wid) # SpecialCases ispec

    def ospec(self):
        return FPSCData(self.width, self.id_wid) # DeNorm ospec

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        smod = FPAddSpecialCasesMod(self.width, self.id_wid)
        dmod = FPAddDeNormMod(self.width, self.id_wid)

        chain = StageChain([smod, dmod])
        chain.setup(m, i)

        # only needed for break-out (early-out)
        # self.out_do_z = smod.o.out_do_z

        self.o = dmod.o

    def process(self, i):
        return self.o

    def action(self, m):
        # for break-out (early-out)
        #with m.If(self.out_do_z):
        #    m.next = "put_z"
        #with m.Else():
            m.d.sync += self.out.eq(self.process(None))
            m.next = "align"



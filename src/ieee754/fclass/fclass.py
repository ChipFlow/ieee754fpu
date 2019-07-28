# IEEE754 FCLASS Module
# Copyright (C) 2019 Luke Kenneth Casson Leighon <lkcl@lkcl.net>

from nmigen import Module, Signal, Cat, Elaboratable

from ieee754.fpcommon.getop import FPADDBaseData
from ieee754.fpcommon.pack import FPPackData
from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord


class FPClassMod(Elaboratable):
    """ obtains floating point information (zero, nan, inf etc.)
    """
    def __init__(self, in_pspec, out_pspec):
        self.in_pspec = in_pspec
        self.out_pspec = out_pspec
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPADDBaseData(self.in_pspec)

    def ospec(self):
        return FPPackData(self.out_pspec)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.fclass = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        # decode incoming FP number
        print("in_width out", self.in_pspec.width,
              self.out_pspec.width)
        a1 = FPNumBaseRecord(self.in_pspec.width, False)
        print("a1", a1.width, a1.rmw, a1.e_width, a1.e_start, a1.e_end)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.d.comb += a1.v.eq(self.i.a)

        # FCLASS: work out the "type" of the FP number

        finite_nzero = Signal(reset_less=True)
        msbzero = Signal(reset_less=True)
        is_sig_nan = Signal(reset_less=True)
        # XXX use *REAL* mantissa width to detect msb.
        # XXX do NOT use a1.m_msbzero because it has extra bitspace
        m.d.comb += msbzero.eq(a1.m[a1.rmw-1] == 0) # sigh, 1 extra msb bit
        m.d.comb += finite_nzero.eq(~a1.is_nan & ~a1.is_inf & ~a1.is_zero)
        m.d.comb += is_sig_nan.eq(a1.exp_128 & (msbzero) & (~a1.m_zero))
        subnormal = a1.exp_n127

        # this is hardware-optimal but very hard to understand.
        # see unit test test_fclass_pipe.py fclass() for what's
        # going on.
        m.d.comb += self.o.z.eq(Cat(
                    a1.s   & a1.is_inf,                 # | −inf.
                    a1.s   & finite_nzero & ~subnormal, # | -normal number.
                    a1.s   & finite_nzero &  subnormal, # | -subnormal number.
                    a1.s & a1.is_zero,                  # | −0.
                    ~a1.s & a1.is_zero,                 # | +0.
                    ~a1.s & finite_nzero &  subnormal,  # | +subnormal number.
                    ~a1.s & finite_nzero & ~subnormal,  # | +normal number.
                    ~a1.s & a1.is_inf,                  # | +inf.
                    is_sig_nan,                         # | a signaling NaN.
                    a1.is_nan & ~is_sig_nan))           # | a quiet NaN

        m.d.comb += self.o.ctx.eq(self.i.ctx)

        return m

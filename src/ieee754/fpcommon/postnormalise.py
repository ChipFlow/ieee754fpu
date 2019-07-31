# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux
from nmigen.cli import main, verilog
from math import log

from nmutil.pipemodbase import FPModBase
from ieee754.fpcommon.fpbase import (Overflow, OverflowMod,
                                     FPNumBase, FPNumBaseRecord)
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.getop import FPPipeContext
from ieee754.fpcommon.msbhigh import FPMSBHigh
from ieee754.fpcommon.exphigh import FPEXPHigh
from ieee754.fpcommon.postcalc import FPAddStage1Data


class FPNorm1Data:

    def __init__(self, pspec):
        width = pspec.width
        self.roundz = Signal(reset_less=True, name="norm1_roundz")
        self.z = FPNumBaseRecord(width, False, name="z")
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid

    def eq(self, i):
        ret = [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
               self.roundz.eq(i.roundz), self.ctx.eq(i.ctx)]
        return ret


class FPNorm1ModSingle(FPModBase):

    def __init__(self, pspec, e_extra=False):
        self.e_extra = e_extra
        super().__init__(pspec, "normalise_1")

    def ispec(self):
        return FPAddStage1Data(self.pspec, e_extra=self.e_extra)

    def ospec(self):
        return FPNorm1Data(self.pspec)

    def elaborate(self, platform):
        m = Module()

        of = OverflowMod("norm1of_")

        #m.submodules.norm1_out_z = self.o.z
        m.submodules.norm1_out_overflow = of
        #m.submodules.norm1_in_z = self.i.z
        #m.submodules.norm1_in_overflow = self.i.of

        i = self.ispec()
        i.of.guard.name = "norm1_i_of_guard"
        i.of.round_bit.name = "norm1_i_of_roundbit"
        i.of.sticky.name = "norm1_i_of_sticky"
        i.of.m0.name = "norm1_i_of_m0"
        m.submodules.norm1_insel_z = insel_z = FPNumBase(i.z)
        #m.submodules.norm1_insel_overflow = iof = OverflowMod("iof")

        espec = (len(insel_z.e), True)
        mwid = self.o.z.m_width+2

        msr = FPEXPHigh(mwid+2, espec[0])
        m.submodules.norm_exp = msr

        msb = FPMSBHigh(mwid+1, espec[0], True)
        m.submodules.norm_msb = msb

        m.d.comb += i.eq(self.i)
        # initialise out from in (overridden below)
        m.d.comb += self.o.z.eq(insel_z)
        m.d.comb += Overflow.eq(of, i.of)
        # normalisation increase/decrease conditions
        decrease = Signal(reset_less=True)
        increase = Signal(reset_less=True)
        m.d.comb += decrease.eq(insel_z.m_msbzero & insel_z.exp_gt_n126)
        m.d.comb += increase.eq(insel_z.exp_lt_n126)
        # decrease exponent
        with m.If(~self.i.out_do_z):
            # concatenate s/r/g with mantissa
            temp_m = Signal(mwid+2, reset_less=True)
            m.d.comb += temp_m.eq(Cat(i.of.sticky, i.of.round_bit, i.of.guard,
                                      insel_z.m)),

            with m.If(decrease):
                # make sure that the amount to decrease by does NOT
                # go below the minimum non-INF/NaN exponent
                m.d.comb += msb.limclz.eq(insel_z.exp_sub_n126)
                m.d.comb += [
                    # inputs: mantissa and exponent
                    msb.m_in.eq(temp_m),
                    msb.e_in.eq(insel_z.e),

                    # outputs: mantissa first (s/r/g/m[3:])
                    self.o.z.m.eq(msb.m_out[3:]),    # exclude bits 0&1
                    of.m0.eq(msb.m_out[3]),          # copy of mantissa[0]
                    # overflow in bits 0..1: got shifted too (leave sticky)
                    of.guard.eq(msb.m_out[2]),       # guard
                    of.round_bit.eq(msb.m_out[1]),   # round
                    # now exponent out
                    self.o.z.e.eq(msb.e_out),
                ]
            # increase exponent
            with m.Elif(increase):
                ediff_n126 = Signal(espec, reset_less=True)
                m.d.comb += [
                    # concatenate
                    ediff_n126.eq(insel_z.fp.N126 - insel_z.e),
                    # connect multi-shifter to inp/out m/e (and ediff)
                    msr.m_in.eq(temp_m),
                    msr.e_in.eq(insel_z.e),
                    msr.ediff.eq(ediff_n126),

                    # outputs: mantissa first (s/r/g/m[3:])
                    self.o.z.m.eq(msr.m_out[3:]),
                    of.m0.eq(msr.m_out[3]),   # copy of mantissa[0]
                    # overflow in bits 0..2: got shifted too (leave sticky)
                    of.guard.eq(msr.m_out[2]),     # guard
                    of.round_bit.eq(msr.m_out[1]),  # round
                    of.sticky.eq(msr.m_out[0]),    # sticky
                    # now exponent
                    self.o.z.e.eq(msr.e_out),
                ]

        m.d.comb += self.o.roundz.eq(of.roundz_out)
        m.d.comb += self.o.ctx.eq(self.i.ctx)
        m.d.comb += self.o.out_do_z.eq(self.i.out_do_z)
        m.d.comb += self.o.oz.eq(self.i.oz)

        return m


class FPNorm1ModMulti:

    def __init__(self, pspec, single_cycle=True):
        self.width = width
        self.in_select = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.in_of = Overflow()
        self.temp_z = FPNumBase(width, False)
        self.temp_of = Overflow()
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()

    def elaborate(self, platform):
        m = Module()

        m.submodules.norm1_out_z = self.out_z
        m.submodules.norm1_out_overflow = self.out_of
        m.submodules.norm1_temp_z = self.temp_z
        m.submodules.norm1_temp_of = self.temp_of
        m.submodules.norm1_in_z = self.in_z
        m.submodules.norm1_in_overflow = self.in_of

        in_z = FPNumBase(self.width, False)
        in_of = Overflow()
        m.submodules.norm1_insel_z = in_z
        m.submodules.norm1_insel_overflow = in_of

        # select which of temp or in z/of to use
        with m.If(self.in_select):
            m.d.comb += in_z.eq(self.in_z)
            m.d.comb += in_of.eq(self.in_of)
        with m.Else():
            m.d.comb += in_z.eq(self.temp_z)
            m.d.comb += in_of.eq(self.temp_of)
        # initialise out from in (overridden below)
        m.d.comb += self.out_z.eq(in_z)
        m.d.comb += self.out_of.eq(in_of)
        # normalisation increase/decrease conditions
        decrease = Signal(reset_less=True)
        increase = Signal(reset_less=True)
        m.d.comb += decrease.eq(in_z.m_msbzero & in_z.exp_gt_n126)
        m.d.comb += increase.eq(in_z.exp_lt_n126)
        m.d.comb += self.out_norm.eq(decrease | increase)  # loop-end
        # decrease exponent
        with m.If(decrease):
            m.d.comb += [
                self.out_z.e.eq(in_z.e - 1),  # DECREASE exponent
                self.out_z.m.eq(in_z.m << 1),  # shift mantissa UP
                self.out_z.m[0].eq(in_of.guard),  # steal guard (was tot[2])
                self.out_of.guard.eq(in_of.round_bit),  # round (was tot[1])
                self.out_of.round_bit.eq(0),        # reset round bit
                self.out_of.m0.eq(in_of.guard),
            ]
        # increase exponent
        with m.Elif(increase):
            m.d.comb += [
                self.out_z.e.eq(in_z.e + 1),  # INCREASE exponent
                self.out_z.m.eq(in_z.m >> 1),  # shift mantissa DOWN
                self.out_of.guard.eq(in_z.m[0]),
                self.out_of.m0.eq(in_z.m[1]),
                self.out_of.round_bit.eq(in_of.guard),
                self.out_of.sticky.eq(in_of.sticky | in_of.round_bit)
            ]

        return m


class FPNorm1Single(FPState):

    def __init__(self, width, id_wid, single_cycle=True):
        FPState.__init__(self, "normalise_1")
        self.mod = FPNorm1ModSingle(width)
        self.o = self.ospec()
        self.out_z = FPNumBase(width, False)
        self.out_roundz = Signal(reset_less=True)

    def ispec(self):
        return self.mod.ispec()

    def ospec(self):
        return self.mod.ospec()

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, i)

    def action(self, m):
        m.next = "round"


class FPNorm1Multi(FPState):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "normalise_1")
        self.mod = FPNorm1ModMulti(width)
        self.stb = Signal(reset_less=True)
        self.ack = Signal(reset=0, reset_less=True)
        self.out_norm = Signal(reset_less=True)
        self.in_accept = Signal(reset_less=True)
        self.temp_z = FPNumBase(width)
        self.temp_of = Overflow()
        self.out_z = FPNumBase(width)
        self.out_roundz = Signal(reset_less=True)

    def setup(self, m, in_z, in_of, norm_stb):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z, in_of, norm_stb,
                       self.in_accept, self.temp_z, self.temp_of,
                       self.out_z, self.out_norm)

        m.d.comb += self.stb.eq(norm_stb)
        # sets to zero when not in normalise_1 state
        m.d.sync += self.ack.eq(0)

    def action(self, m):
        m.d.comb += self.in_accept.eq((~self.ack) & (self.stb))
        m.d.sync += self.temp_of.eq(self.mod.out_of)
        m.d.sync += self.temp_z.eq(self.out_z)
        with m.If(self.out_norm):
            with m.If(self.in_accept):
                m.d.sync += [
                    self.ack.eq(1),
                ]
            with m.Else():
                m.d.sync += self.ack.eq(0)
        with m.Else():
            # normalisation not required (or done).
            m.next = "round"
            m.d.sync += self.ack.eq(1)
            m.d.sync += self.out_roundz.eq(self.mod.out_of.roundz)

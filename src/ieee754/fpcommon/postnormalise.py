# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux, Elaboratable
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import Overflow, FPNumBase, FPNumBaseRecord
from ieee754.fpcommon.fpbase import MultiShiftRMerge
from ieee754.fpcommon.fpbase import FPState
from ieee754.fpcommon.getop import FPPipeContext
from .postcalc import FPAddStage1Data


class FPNorm1Data:

    def __init__(self, pspec):
        width = pspec.width
        self.roundz = Signal(reset_less=True, name="norm1_roundz")
        self.z = FPNumBaseRecord(width, False)
        self.out_do_z = Signal(reset_less=True)
        self.oz = Signal(width, reset_less=True)
        self.ctx = FPPipeContext(pspec)
        self.muxid = self.ctx.muxid

    def eq(self, i):
        ret = [self.z.eq(i.z), self.out_do_z.eq(i.out_do_z), self.oz.eq(i.oz),
                self.roundz.eq(i.roundz), self.ctx.eq(i.ctx)]
        return ret


class FPNorm1ModSingle(Elaboratable):

    def __init__(self, pspec, e_extra=False):
        self.pspec = pspec
        self.e_extra = e_extra
        self.i = self.ispec()
        self.o = self.ospec()

    def ispec(self):
        return FPAddStage1Data(self.pspec, e_extra=self.e_extra)

    def ospec(self):
        return FPNorm1Data(self.pspec)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.normalise_1 = self
        m.d.comb += self.i.eq(i)

    def process(self, i):
        return self.o

    def elaborate(self, platform):
        m = Module()

        mwid = self.o.z.m_width+2
        pe = PriorityEncoder(mwid)
        m.submodules.norm_pe = pe

        of = Overflow()
        m.d.comb += self.o.roundz.eq(of.roundz)

        #m.submodules.norm1_out_z = self.o.z
        #m.submodules.norm1_out_overflow = of
        #m.submodules.norm1_in_z = self.i.z
        #m.submodules.norm1_in_overflow = self.i.of

        i = self.ispec()
        m.submodules.norm1_insel_z = insel_z = FPNumBase(i.z)
        #m.submodules.norm1_insel_overflow = i.of

        espec = (len(insel_z.e), True)
        ediff_n126 = Signal(espec, reset_less=True)
        msr = MultiShiftRMerge(mwid+2, espec)
        m.submodules.multishift_r = msr

        m.d.comb += i.eq(self.i)
        # initialise out from in (overridden below)
        m.d.comb += self.o.z.eq(insel_z)
        m.d.comb += of.eq(i.of)
        # normalisation increase/decrease conditions
        decrease = Signal(reset_less=True)
        increase = Signal(reset_less=True)
        m.d.comb += decrease.eq(insel_z.m_msbzero & insel_z.exp_gt_n126)
        m.d.comb += increase.eq(insel_z.exp_lt_n126)
        # decrease exponent
        with m.If(~self.i.out_do_z):
            with m.If(decrease):
                # *sigh* not entirely obvious: count leading zeros (clz)
                # with a PriorityEncoder: to find from the MSB
                # we reverse the order of the bits.
                temp_m = Signal(mwid, reset_less=True)
                temp_s = Signal(mwid+1, reset_less=True)
                clz = Signal((len(insel_z.e), True), reset_less=True)
                # make sure that the amount to decrease by does NOT
                # go below the minimum non-INF/NaN exponent
                limclz = Mux(insel_z.exp_sub_n126 > pe.o, pe.o,
                             insel_z.exp_sub_n126)
                m.d.comb += [
                    # cat round and guard bits back into the mantissa
                    temp_m.eq(Cat(i.of.round_bit, i.of.guard, insel_z.m)),
                    pe.i.eq(temp_m[::-1]),          # inverted
                    clz.eq(limclz),                 # count zeros from MSB down
                    temp_s.eq(temp_m << clz),       # shift mantissa UP
                    self.o.z.e.eq(insel_z.e - clz),  # DECREASE exponent
                    self.o.z.m.eq(temp_s[2:]),    # exclude bits 0&1
                    of.m0.eq(temp_s[2]),          # copy of mantissa[0]
                    # overflow in bits 0..1: got shifted too (leave sticky)
                    of.guard.eq(temp_s[1]),       # guard
                    of.round_bit.eq(temp_s[0]),   # round
                ]
            # increase exponent
            with m.Elif(increase):
                temp_m = Signal(mwid+1, reset_less=True)
                m.d.comb += [
                    temp_m.eq(Cat(i.of.sticky, i.of.round_bit, i.of.guard,
                                  insel_z.m)),
                    ediff_n126.eq(insel_z.fp.N126 - insel_z.e),
                    # connect multi-shifter to inp/out mantissa (and ediff)
                    msr.inp.eq(temp_m),
                    msr.diff.eq(ediff_n126),
                    self.o.z.m.eq(msr.m[3:]),
                    of.m0.eq(msr.m[3]),   # copy of mantissa[0]
                    # overflow in bits 0..1: got shifted too (leave sticky)
                    of.guard.eq(msr.m[2]),     # guard
                    of.round_bit.eq(msr.m[1]), # round
                    of.sticky.eq(msr.m[0]),    # sticky
                    self.o.z.e.eq(insel_z.e + ediff_n126),
                ]

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
        m.d.comb += self.out_norm.eq(decrease | increase) # loop-end
        # decrease exponent
        with m.If(decrease):
            m.d.comb += [
                self.out_z.e.eq(in_z.e - 1),  # DECREASE exponent
                self.out_z.m.eq(in_z.m << 1), # shift mantissa UP
                self.out_z.m[0].eq(in_of.guard), # steal guard (was tot[2])
                self.out_of.guard.eq(in_of.round_bit), # round (was tot[1])
                self.out_of.round_bit.eq(0),        # reset round bit
                self.out_of.m0.eq(in_of.guard),
            ]
        # increase exponent
        with m.Elif(increase):
            m.d.comb += [
                self.out_z.e.eq(in_z.e + 1),  # INCREASE exponent
                self.out_z.m.eq(in_z.m >> 1), # shift mantissa DOWN
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
        m.d.sync += self.ack.eq(0) # sets to zero when not in normalise_1 state

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



# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat,
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog
from math import log

from ieee754.fpcommon.fpbase import Overflow, FPNumBase
from ieee754.fpcommon.fpbase import MultiShiftRMerge

from ieee754.fpcommon.fpbase import FPState


class FPNormaliseModSingle:

    def __init__(self, width):
        self.width = width
        self.in_z = self.ispec()
        self.out_z = self.ospec()

    def ispec(self):
        return FPNumBase(self.width, False)

    def ospec(self):
        return FPNumBase(self.width, False)

    def setup(self, m, i):
        """ links module to inputs and outputs
        """
        m.submodules.normalise = self
        m.d.comb += self.i.eq(i)

    def elaborate(self, platform):
        m = Module()

        mwid = self.out_z.m_width+2
        pe = PriorityEncoder(mwid)
        m.submodules.norm_pe = pe

        m.submodules.norm1_out_z = self.out_z
        m.submodules.norm1_in_z = self.in_z

        in_z = FPNumBase(self.width, False)
        in_of = Overflow()
        m.submodules.norm1_insel_z = in_z
        m.submodules.norm1_insel_overflow = in_of

        espec = (len(in_z.e), True)
        ediff_n126 = Signal(espec, reset_less=True)
        msr = MultiShiftRMerge(mwid, espec)
        m.submodules.multishift_r = msr

        m.d.comb += in_z.eq(self.in_z)
        m.d.comb += in_of.eq(self.in_of)
        # initialise out from in (overridden below)
        m.d.comb += self.out_z.eq(in_z)
        m.d.comb += self.out_of.eq(in_of)
        # normalisation decrease condition
        decrease = Signal(reset_less=True)
        m.d.comb += decrease.eq(in_z.m_msbzero)
        # decrease exponent
        with m.If(decrease):
            # *sigh* not entirely obvious: count leading zeros (clz)
            # with a PriorityEncoder: to find from the MSB
            # we reverse the order of the bits.
            temp_m = Signal(mwid, reset_less=True)
            temp_s = Signal(mwid+1, reset_less=True)
            clz = Signal((len(in_z.e), True), reset_less=True)
            m.d.comb += [
                # cat round and guard bits back into the mantissa
                temp_m.eq(Cat(in_of.round_bit, in_of.guard, in_z.m)),
                pe.i.eq(temp_m[::-1]),          # inverted
                clz.eq(pe.o),                   # count zeros from MSB down
                temp_s.eq(temp_m << clz),       # shift mantissa UP
                self.out_z.e.eq(in_z.e - clz),  # DECREASE exponent
                self.out_z.m.eq(temp_s[2:]),    # exclude bits 0&1
            ]

        return m



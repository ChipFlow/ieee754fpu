# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import MultiShiftRMerge


class FPEXPHigh(Elaboratable):

    def __init__(self, m_width, e_width):
        self.m_width = m_width
        self.e_width = e_width
        self.ediff = Signal((e_width, True), reset_less=True)

        self.m_in = Signal(m_width, reset_less=True)
        self.e_in = Signal((e_width, True), reset_less=True)
        self.m_out = Signal(m_width, reset_less=True)
        self.e_out = Signal((e_width, True), reset_less=True)

    def elaborate(self, platform):
        m = Module()

        espec = (self.e_width, True)
        mwid = self.m_width

        msr = MultiShiftRMerge(mwid, espec)
        m.submodules.multishift_r = msr

        m.d.comb += [
            # connect multi-shifter to inp/out mantissa (and ediff)
            msr.inp.eq(self.m_in),
            msr.diff.eq(self.ediff),
            self.m_out.eq(msr.m),
            self.e_out.eq(self.e_in + self.ediff),
        ]


        return m



""" module for adjusting a mantissa and exponent so that the MSB is always 1
"""

from nmigen import Module, Signal, Mux, Elaboratable
from nmigen.lib.coding import PriorityEncoder


class FPMSBHigh(Elaboratable):
    """ makes the top mantissa bit hi (i.e. shifts until it is)

        NOTE: this does NOT do any kind of checks.  do not pass in
        zero (empty) stuff, and it's best to check if the MSB is
        already 1 before calling it.  although it'll probably work
        in both cases...

        * exponent is signed
        * mantissa is unsigned.
        * loprop: propagates the low bit (LSB) on the shift
        * limclz: use this to limit the amount of shifting.

        examples:
        exp = -30, mantissa = 0b00011 - output: -33, 0b11000
        exp =   2, mantissa = 0b01111 - output:   1, 0b11110
    """
    def __init__(self, m_width, e_width, limclz=False, loprop=False):
        self.m_width = m_width
        self.e_width = e_width
        self.loprop = loprop
        self.limclz = limclz and Signal((e_width, True), reset_less=True)

        self.m_in = Signal(m_width, reset_less=True)
        self.e_in = Signal((e_width, True), reset_less=True)
        self.m_out = Signal(m_width, reset_less=True)
        self.e_out = Signal((e_width, True), reset_less=True)

    def elaborate(self, platform):
        m = Module()

        mwid = self.m_width
        pe = PriorityEncoder(mwid)
        m.submodules.pe = pe

        # *sigh* not entirely obvious: count leading zeros (clz)
        # with a PriorityEncoder.  to find from the MSB
        # we reverse the order of the bits.  it would be better if PE
        # took a "reverse" argument.

        clz = Signal((len(self.e_out), True), reset_less=True)
        temp = Signal(mwid, reset_less=True)
        if self.loprop:
            temp_r = Signal(mwid, reset_less=True)
            with m.If(self.m_in[0]):
                # propagate low bit: do an ASL basically, except
                # i can't work out how to do it in nmigen sigh
                m.d.comb += temp_r.eq((self.m_in[0] << clz) - 1)

        # limclz sets a limit (set by the exponent) on how far M can be shifted
        # this can be used to ensure that near-zero numbers don't then have
        # to be shifted *back* (e < -126 in the case of FP32 for example)
        if self.limclz is not False:
            limclz = Mux(self.limclz > pe.o, pe.o, self.limclz)
        else:
            limclz = pe.o

        m.d.comb += [
            pe.i.eq(self.m_in[::-1]),     # inverted
            clz.eq(limclz),          # count zeros from MSB down
            temp.eq((self.m_in << clz)),  # shift mantissa UP
            self.e_out.eq(self.e_in - clz), # DECREASE exponent
        ]
        if self.loprop:
            m.d.comb += self.m_out.eq(temp | temp_r)
        else:
            m.d.comb += self.m_out.eq(temp),

        return m

""" module for adjusting a mantissa and exponent so that the MSB is always 1
"""

from nmigen import Module, Signal, Elaboratable
from nmigen.lib.coding import PriorityEncoder


class FPMSBHigh(Elaboratable):
    """ makes the top mantissa bit hi (i.e. shifts until it is)

        NOTE: this does NOT do any kind of checks.  do not pass in
        zero (empty) stuff, and it's best to check if the MSB is
        already 1 before calling it.  although it'll probably work
        in both cases...

        * exponent is signed
        * mantissa is unsigned.

        examples:
        exp = -30, mantissa = 0b00011 - output: -33, 0b11000
        exp =   2, mantissa = 0b01111 - output:   1, 0b11110
    """
    def __init__(self, m_width, e_width):
        self.m_width = m_width
        self.e_width = e_width

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
        # with a PriorityEncoder: to find from the MSB
        # we reverse the order of the bits.
        temp = Signal(mwid, reset_less=True)
        clz = Signal((len(self.e_out), True), reset_less=True)
        m.d.comb += [
            pe.i.eq(insel.m[::-1]),       # inverted
            clz.eq(pe.o),                 # count zeros from MSB down
            temp.eq((self.m_in << clz)),  # shift mantissa UP
            self.e_out.eq(insel.e - clz), # DECREASE exponent
            self.m_out.eq(temp),
        ]


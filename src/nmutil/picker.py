""" Priority Picker: optimised back-to-back PriorityEncoder and Decoder

    The input is N bits, the output is N bits wide and only one is
    enabled.
"""

from nmigen import Module, Signal, Cat, Elaboratable

class PriorityPicker(Elaboratable):
    """ implements a priority-picker.  input: N bits, output: N bits
    """
    def __init__(self, wid):
        self.wid = wid
        # inputs
        self.i = Signal(wid, reset_less=True)
        self.o = Signal(wid, reset_less=True)

    def elaborate(self, platform):
        m = Module()

        res = []
        ni = Signal(self.wid, reset_less = True)
        m.d.comb += ni.eq(~self.i)
        for i in range(0, self.wid):
            t = Signal(reset_less = True)
            res.append(t)
            if i == 0:
                m.d.comb += t.eq(self.i[i])
            else:
                m.d.comb += t.eq(~Cat(ni[i], *self.i[:i]).bool())

        # we like Cat(*xxx).  turn lists into concatenated bits
        m.d.comb += self.o.eq(Cat(*res))

        return m

    def __iter__(self):
        yield self.i
        yield self.o

    def ports(self):
        return list(self)

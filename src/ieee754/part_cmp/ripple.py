# need to ripple the starting LSB of each partition up through the
# rest of the partition.  a Mux on the partition gate therefore selects
# either the current "thing" being propagated, or, if the gate is set open,
# will select the current bit from the input.
#
# this is actually a useful function, it's one of "set before first" or
# "set after first" from vector predication processing.

from nmigen import Signal, Module, Elaboratable, Mux


class RippleLSB(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.results_in = Signal(width, reset_less=True)
        self.gates = Signal(width-1, reset_less=True)

        self.output = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = self.width

        current_result = self.results_in[0]
        comb += self.output[0].eq(current_result)

        for i in range(width-1):
            cur = Signal("cur%d" % i)
            comb += cur.eq(current_result)
            current_result = Mux(self.gates[i], self.results_in[i+1], cur)
            comb += self.output[i+1].eq(current_result)

        return m

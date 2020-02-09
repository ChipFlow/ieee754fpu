# need to ripple the starting LSB of each partition up through the
# rest of the partition.  a Mux on the partition gate therefore selects
# either the current "thing" being propagated, or, if the gate is set open,
# will select the current bit from the input.
#
# this is actually a useful function, it's one of "set before first" or
# "set after first" from vector predication processing.

from nmigen import Signal, Module, Elaboratable, Mux, Cat
from nmigen.cli import main


class RippleLSB(Elaboratable):
    """RippleLSB

    based on a partition mask, the LSB is "rippled" (duplicated)
    up to the beginning of the next partition.
    """
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
            cur = Mux(self.gates[i], self.results_in[i+1], self.output[i])
            comb += self.output[i+1].eq(cur)

        return m


class MoveMSBDown(Elaboratable):
    """MoveMSBDown

    based on a partition mask, moves the MSB down to the LSB position.
    only the MSB is relevant, other bits are ignored.  works by first
    rippling the MSB across the entire partition (TODO: split that out
    into its own useful module), then ANDs the (new) LSB with the
    partition mask to isolate it.
    """
    def __init__(self, width):
        self.width = width
        self.results_in = Signal(width, reset_less=True)
        self.gates = Signal(width-1, reset_less=True)
        self.output = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = self.width
        intermed = Signal(width, reset_less=True)

        # first propagate MSB down until the nearest partition gate
        comb += intermed[-1].eq(self.results_in[-1]) # start at MSB
        for i in range(width-2, -1, -1):
            cur = Mux(self.gates[i], self.results_in[i], intermed[i+1])
            comb += intermed[i].eq(cur)

        # now only select those bits where the mask starts
        out = [intermed[0]] # LSB of first part always set
        for i in range(width-1): # length of partition gates
            out.append(self.gates[i] & intermed[i+1])
        comb += self.output.eq(Cat(*out))

        return m


if __name__ == "__main__":
    # python3 ieee754/part_cmp/ripple.py generate -t il > ripple.il
    # then check with yosys "read_ilang ripple.il; show top"
    alu = MoveMSBDown(width=4)
    main(alu, ports=[alu.results_in, alu.gates, alu.output])


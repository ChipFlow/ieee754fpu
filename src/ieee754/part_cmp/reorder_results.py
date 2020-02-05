# gt_combiner returns results that are in the wrong order from how
# they need to be. Specifically, if the partition gates are open, the
# bits need to be reversed through the width of the partition. This
# module does that
from nmigen import Signal, Module, Elaboratable, Mux
from ieee754.part_mul_add.partpoints import PartitionPoints

class ReorderResults(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.results_in = Signal(width, reset_less=True)
        self.gates = Signal(width-1, reset_less=True)

        self.output = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = self.width

        current_result = self.results_in[-1]

        for i in range(width-2, -1, -1):  # counts down from width-1 to 0
            cur = Signal()
            comb += cur.eq(current_result)
            comb += self.output[i+1].eq(cur & self.gates[i])
            current_result = Mux(self.gates[i], self.results_in[i], cur)

            comb += self.output[0].eq(current_result)
        return m

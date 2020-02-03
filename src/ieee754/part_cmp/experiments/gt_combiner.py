from nmigen import Signal, Module, Elaboratable, Mux
from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_cmp.experiments.eq_combiner import Twomux


# This is similar to EQCombiner, except that for a greater than
# comparison, it needs to deal with both the greater than and equals
# signals from each partition. The signals are combined using a
# cascaded AND/OR to give the following effect:
# When a partition is open, the output is set if either the current
# partition's greater than flag is set, or the current partition's
# equal flag is set AND the previous partition's greater than output
# is true
class GTCombiner(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.mux_input = Signal(reset_less=True)  # right hand side mux input
        self.eqs = Signal(width, reset_less=True) # the flags for EQ
        self.gts = Signal(width, reset_less=True) # the flags for GT
        self.gates = Signal(width-1, reset_less=True)
        self.outputs = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        previnput = self.gts[-1] | (self.eqs[-1] & self.mux_input)
        for i in range(self.width-1, 0, -1): # counts down from width-1 to 1
            m.submodules["mux{}".format(i)] = mux = Twomux()

            comb += mux.ina.eq(previnput)
            comb += mux.inb.eq(self.mux_input)
            comb += mux.sel.eq(self.gates[i-1])
            comb += self.outputs[i].eq(mux.outb)
            previnput =  self.gts[i-1] | (self.eqs[i-1] & mux.outa)

        comb += self.outputs[0].eq(previnput)

        return m

    def ports(self):
        return [self.eqs, self.gts, self.gates, self.outputs]

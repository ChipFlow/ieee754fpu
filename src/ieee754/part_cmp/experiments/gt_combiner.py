from nmigen import Signal, Module, Elaboratable, Mux
from ieee754.part_mul_add.partpoints import PartitionPoints

class Combiner(Elaboratable):

    def __init__(self):
        self.ina = Signal()
        self.inb = Signal()
        self.sel = Signal()
        self.outa = Signal()
        self.outb = Signal()

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        comb += self.outa.eq(Mux(self.sel, self.inb, self.ina))
        comb += self.outb.eq(self.sel & self.ina)

        return m

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
        self.aux_input = Signal(reset_less=True)  # right hand side mux input
        self.gt_en = Signal(reset_less=True)      # enable or disable the gt signal
        self.eqs = Signal(width, reset_less=True) # the flags for EQ
        self.gts = Signal(width, reset_less=True) # the flags for GT
        self.gates = Signal(width-1, reset_less=True)
        self.outputs = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        previnput = (self.gts[-1] & self.gt_en) | (self.eqs[-1] & self.aux_input)

        for i in range(self.width-1, 0, -1): # counts down from width-1 to 1
            m.submodules["mux%d" % i] = mux = Combiner()

            comb += mux.ina.eq(previnput)
            comb += mux.inb.eq(self.aux_input)
            comb += mux.sel.eq(self.gates[i-1])
            comb += self.outputs[i].eq(mux.outb)
            previnput = (self.gts[i-1] & self.gt_en) | (self.eqs[i-1] & mux.outa)

        comb += self.outputs[0].eq(previnput)

        return m

    def ports(self):
        return [self.eqs, self.gts, self.gates, self.outputs]

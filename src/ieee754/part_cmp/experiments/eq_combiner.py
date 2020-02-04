from nmigen import Signal, Module, Elaboratable, Mux
from ieee754.part_mul_add.partpoints import PartitionPoints


class Twomux(Elaboratable):

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
        comb += self.outb.eq(Mux(self.sel, self.ina, self.inb))

        return m

#This module is a test of a better way to implement combining the
#signals for equals for the partitioned equality module than
#equals.py's giant switch statement. The idea is to use a tree of two
#input/two output multiplexors and or gates to select whether each
#signal is or isn't combined with its neighbors.

class EQCombiner(Elaboratable):

    def __init__(self, width):
        self.width = width
        self.neqs = Signal(width, reset_less=True)
        self.gates = Signal(width-1, reset_less=True)
        self.outputs = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        previnput = self.neqs[-1]

        for i in range(self.width-1, 0, -1): # counts down from width-1 to 1
            m.submodules["mux%d" % i] = mux = Twomux()

            comb += mux.ina.eq(previnput)
            comb += mux.inb.eq(0)
            comb += mux.sel.eq(~self.gates[i-1])
            comb += self.outputs[i].eq(mux.outa ^ self.gates[i-1])
            previnput = mux.outb | self.neqs[i-1]
        
        comb += self.outputs[0].eq(~previnput)

        return m

    def ports(self):
        return [self.neqs, self.gates, self.outputs]

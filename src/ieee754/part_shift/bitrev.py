from nmigen import Signal, Module, Elaboratable, Cat, Mux

class GatedBitReverse(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.data = Signal(width, reset_less=True)
        self.reverse_en = Signal(reset_less=True)
        self.output = Signal(width, reset_less=True)
    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = self.width

        for i in range(width):
            with m.If(self.reverse_en):
                comb += self.output[i].eq(self.data[width-i-1])
            with m.Else():
                comb += self.output[i].eq(self.data[i])

        return m

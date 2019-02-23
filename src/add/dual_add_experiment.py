from nmigen import *
from nmigen.cli import main

from nmigen_add_experiment import FPADD
from fpbase import FPOp


class Adder:
    def __init__(self, width):
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.a + self.b)
        return m


class Subtractor:
    def __init__(self, width):
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.a - self.b)
        return m


class ALU:
    def __init__(self, width):
        #self.op  = Signal()
        self.a   = FPOp(width)
        self.b   = FPOp(width)
        self.c   = FPOp(width)
        self.z   = FPOp(width)

        self.add1 = FPADD(width)
        self.add2 = FPADD(width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.add1 = self.add1
        m.submodules.add2 = self.add2
        m.d.comb += [
            # join add1 a to a
            self.add1.in_a.v.eq(self.a.v),
            self.add1.in_a.stb.eq(self.a.stb),
            # join add1 b to b
            self.add1.in_b.v.eq(self.b.v),
            self.add1.in_b.stb.eq(self.b.stb),
            # join add2 a to c
            self.add2.in_a.v.eq(self.c.v),
            self.add2.in_a.stb.eq(self.c.stb),
            # join add2 b to add1 z
            self.add2.in_b.v.eq(self.add1.out_z.v),
            self.add2.in_b.stb.eq(self.add1.out_z.stb),
        ]
        m.d.sync += [
            # join add1 a to a
            self.add1.in_a.ack.eq(self.a.ack),
            # join add1 b to b
            self.add1.in_b.ack.eq(self.b.ack),
            # join add2 a to c
            self.add2.in_a.ack.eq(self.c.ack),
            # join add2 b to add1 z
            self.add2.in_b.ack.eq(self.add1.out_z.ack),
        ]
        #with m.If(self.op):
        #    m.d.comb += self.o.eq(self.sub.o)
        #with m.Else():
        #    m.d.comb += self.o.eq(self.add.o)
        return m


if __name__ == "__main__":
    alu = ALU(width=16)
    main(alu, ports=alu.a.ports() + \
                     alu.b.ports() + \
                     alu.c.ports() + \
                     alu.z.ports())

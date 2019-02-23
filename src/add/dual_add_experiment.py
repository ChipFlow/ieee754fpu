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
            # join add1 a to a: add1.in_a = a
            self.add1.in_a.v.eq(self.a.v),
            self.add1.in_a.stb.eq(self.a.stb),
            self.a.ack.eq(self.add1.in_a.ack),
            # join add1 b to b: add1.in_b = b
            self.add1.in_b.v.eq(self.b.v),
            self.add1.in_b.stb.eq(self.b.stb),
            self.b.ack.eq(self.add1.in_b.ack),
            # join add2 a to c: add2.in_a = c
            self.add2.in_a.v.eq(self.c.v),
            self.add2.in_a.stb.eq(self.c.stb),
            self.c.ack.eq(self.add2.in_a.ack),
            # join add2 b to add1 z: add2.in_b = add1.out_z
            self.add2.in_b.v.eq(self.add1.out_z.v),
            self.add2.in_b.stb.eq(self.add1.out_z.stb),
            self.add1.out_z.ack.eq(self.add2.in_b.ack),
            # join output from add2 to z: z = add2.out_z
            self.z.v.eq(self.add2.out_z.v),
            self.z.stb.eq(self.add2.out_z.stb),
            self.add2.out_z.ack.eq(self.z.ack),
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

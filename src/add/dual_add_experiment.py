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
        self.int_stb = Signal()

        self.add1 = FPADD(width)
        self.add2 = FPADD(width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.add1 = self.add1
        m.submodules.add2 = self.add2
        # join add1 a to a: add1.in_a = a
        m.d.comb += self.add1.in_a.chain_from(self.a)
        # join add1 b to b: add1.in_b = b
        m.d.comb += self.add1.in_b.chain_from(self.b)
        # join add2 a to c: add2.in_a = c
        m.d.comb += self.add2.in_a.chain_from(self.c)
        # join add2 b to add1 z: add2.in_b = add1.out_z
        m.d.comb += self.add2.in_b.chain_inv(self.add1.out_z)
        # join output from add2 to z: z = add2.out_z
        m.d.comb += self.z.chain_from(self.add2.out_z)
        # get at add1's stb signal
        m.d.comb += self.int_stb.eq(self.add1.out_z.stb)
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

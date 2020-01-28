# Proof of correctness for FSGNJ module
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable
from nmigen.asserts import Assert, Assume
from nmigen.cli import rtlil

from ieee754.fsgnj.fsgnj import FSGNJPipeMod
from ieee754.pipeline import PipelineSpec
import subprocess


# This defines a module to drive the device under test and assert
# properties about its outputs
class FSGNJDriver(Elaboratable):
    def __init__(self, pspec):
        # inputs and outputs
        self.pspec = pspec
        self.a = Signal(pspec.width)
        self.b = Signal(pspec.width)
        self.z = Signal(pspec.width)
        self.opc = Signal(pspec.op_wid)
        self.muxid = Signal(pspec.id_wid)

    def elaborate(self, platform):
        m = Module()

        m.submodules.dut = dut = FSGNJPipeMod(self.pspec)

        # connect up the inputs and outputs. I think these could
        # theoretically be $anyconst/$anysync but I'm not sure nmigen
        # has support for that
        m.d.comb += dut.i.a.eq(self.a)
        m.d.comb += dut.i.b.eq(self.b)
        m.d.comb += dut.i.ctx.op.eq(self.opc)
        m.d.comb += dut.i.muxid.eq(self.muxid)
        m.d.comb += self.z.eq(dut.o.z)

        # Since the RISCV spec doesn't define what FSGNJ with a funct3
        # field of 0b011 throug 0b111 does, they should be ignored.
        m.d.comb += Assume(self.opc != 0b11)

        # The RISCV spec (page 70) says FSGNJ "produces a result that
        # takes all buts except the sign bit from [operand 1]". This
        # asserts that that holds true
        m.d.comb += Assert(self.z[0:31] == self.a[0:31])

        with m.Switch(self.opc):

            # The RISCV Spec (page 70) states that for FSGNJ (opcode
            # 0b00 in this case) "the result's sign bit is [operand
            # 2's] sign bit"
            with m.Case(0b00):
                m.d.comb += Assert(self.z[-1] == self.b[-1])

            # The RISCV Spec (page 70) states that for FSGNJN (opcode
            # 0b01 in this case) "the result's sign bit is the opposite
            # of [operand 2's] sign bit"
            with m.Case(0b01):
                m.d.comb += Assert(self.z[-1] == ~self.b[-1])
            # The RISCV Spec (page 70) states that for FSGNJX (opcode
            # 0b10 in this case) "the result's sign bit is the XOR of
            # the sign bits of [operand 1] and [operand 2]"
            with m.Case(0b10):
                m.d.comb += Assert(self.z[-1] == (self.a[-1] ^ self.b[-1]))

        return m

    def ports(self):
        return [self.a, self.b, self.z, self.opc, self.muxid]


def run_test():
    m = FSGNJDriver(PipelineSpec(32, 2, 2))

    il = rtlil.convert(m, ports=m.ports())
    with open("proof.il", "w") as f:
        f.write(il)
    p = subprocess.Popen(['sby', '-f', 'proof.sby'],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    if p.wait() == 0:
        out, err = p.communicate()
        print("Proof successful!")
        print(out.decode('utf-8'))
    else:
        print("Proof failed")
        out, err = p.communicate()
        print(out.decode('utf-8'))
        print(err.decode('utf-8'))


if __name__ == "__main__":
    run_test()

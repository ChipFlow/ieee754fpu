# Proof of correctness for FPMAX module
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable
from nmigen.asserts import Assert, Assume
from nmigen.cli import rtlil

from ieee754.fpcommon.fpbase import FPNumDecode, FPNumBaseRecord
from ieee754.fpmax.fpmax import FPMAXPipeMod
from ieee754.pipeline import PipelineSpec
import subprocess


# This defines a module to drive the device under test and assert
# properties about its outputs
class FPMAXDriver(Elaboratable):
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

        m.submodules.dut = dut = FPMAXPipeMod(self.pspec)

        a1 = FPNumBaseRecord(self.pspec.width, False)
        b1 = FPNumBaseRecord(self.pspec.width, False)
        z1 = FPNumBaseRecord(self.pspec.width, False)
        m.submodules.sc_decode_a = a1 = FPNumDecode(None, a1)
        m.submodules.sc_decode_b = b1 = FPNumDecode(None, b1)
        m.submodules.sc_decode_z = z1 = FPNumDecode(None, z1)

        m.d.comb += [a1.v.eq(self.a),
                     b1.v.eq(self.b),
                     z1.v.eq(self.z)]

        m.d.comb += Assert((z1.v == a1.v) | (z1.v == b1.v) | (z1.v == a1.fp.nan2(0)))

        # connect up the inputs and outputs. I think these could
        # theoretically be $anyconst/$anysync but I'm not sure nmigen
        # has support for that
        m.d.comb += dut.i.a.eq(self.a)
        m.d.comb += dut.i.b.eq(self.b)
        m.d.comb += dut.i.ctx.op.eq(self.opc)
        m.d.comb += dut.i.muxid.eq(self.muxid)
        m.d.comb += self.z.eq(dut.o.z)


        return m

    def ports(self):
        return [self.a, self.b, self.z, self.opc, self.muxid]


def run_test(bits=32):
    m = FPMAXDriver(PipelineSpec(bits, 2, 1))

    il = rtlil.convert(m, ports=m.ports())
    with open("proof.il", "w") as f:
        f.write(il)
    p = subprocess.Popen(['sby', '-f', 'proof.sby'],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    if p.wait() == 0:
        out, _ = p.communicate()
        print("Proof successful!")
        print(out.decode('utf-8'))
    else:
        print("Proof failed")
        out, err = p.communicate()
        print(out.decode('utf-8'))
        print(err.decode('utf-8'))


if __name__ == "__main__":
    run_test(bits=32)

from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Passive
from nmigen.test.utils import FHDLTestCase
from nmigen.cli import rtlil
from sfpy import Float32

from ieee754.cordic.fp_pipeline import FPCordicBasePipe
from ieee754.cordic.fp_pipe_data import FPCordicPipeSpec
import unittest
import math
import random


class SinCosTestCase(FHDLTestCase):
    def run_test(self, inputs):
        m = Module()
        pspec = FPCordicPipeSpec(width=32, rounds_per_stage=4, num_rows=1)
        m.submodules.dut = dut = FPCordicBasePipe(pspec)

        for port in dut.ports():
            print ("port", port)

        # vl = rtlil.convert(dut, ports=dut.ports())
        # with open("test_cordic_pipe_sin_cos.il", "w") as f:
        #     f.write(vl)

        z = Signal(dut.p.data_i.a.shape())
        z_valid = Signal()
        ready = Signal()

        m.d.comb += [
            dut.p.data_i.a.eq(z),
            dut.p.valid_i.eq(z_valid),
            dut.n.ready_i.eq(ready),
            ]

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def writer_process():
            for val in inputs:
                print(val)
                yield z.eq(val.bits)
                yield z_valid.eq(1)
                yield ready.eq(1)
                yield

        sim.add_sync_process(writer_process)
        with sim.write_vcd("fp_pipeline.vcd", "fp_pipeline.gtkw", traces=[
                z]):
            sim.run()

    def test_rand(self):
        fracbits = 16
        M = (1 << fracbits)
        ZMAX = int(round(M * math.pi/2))
        inputs = []
        for i in range(-5, 10, 1):
            if i < 0:
                inputs.append(Float32(-2.0**(-abs(i))))
            else:
                inputs.append(Float32(2.0**(-abs(i))))
        self.run_test(iter(inputs))


if __name__ == "__main__":
    unittest.main()

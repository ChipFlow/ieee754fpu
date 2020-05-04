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
    def run_test(self, inputs, outputs=iter([])):
        m = Module()
        pspec = FPCordicPipeSpec(width=32, rounds_per_stage=4, num_rows=1)
        m.submodules.dut = dut = FPCordicBasePipe(pspec)


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
                yield z.eq(val.bits)
                yield z_valid.eq(1)
                yield ready.eq(1)
                yield
            for i in range(40):
                yield
        def reader_process():
            while True:
                yield
                vld = yield dut.n.valid_o
                if vld:
                    try:
                        sin, cos = outputs.__next__()
                        result = yield dut.n.data_o.x
                        result = Float32(result)
                        msg = f"cos: expected {cos} got {result}"
                        self.assertLess(abs(result - Float32(cos)),
                                        Float32(2e-7), msg=msg)
                        result = yield dut.n.data_o.y
                        result = Float32(result)
                        msg = f"sin: expected {sin} got {result}"
                        self.assertLess(abs(result - Float32(sin)),
                                        Float32(2e-7), msg=msg)
                    except StopIteration:
                        break

        sim.add_sync_process(writer_process)
        sim.add_sync_process(reader_process)
        with sim.write_vcd("fp_pipeline.vcd", "fp_pipeline.gtkw", traces=[
                z]):
            sim.run()

    def test_rand(self):
        inputs = []
        for i in range(20000):
            x = random.uniform(-1, 1)
            inputs.append(Float32(x))
        sines = [math.sin(x * Float32(math.pi/2)) for x in inputs]
        cosines = [math.cos(x * Float32(math.pi/2)) for x in inputs]
        outputs = zip(sines, cosines)
        self.run_test(iter(inputs), outputs=iter(outputs))

    def test_pi_2(self):
        inputs = [Float32(0.5), Float32(1/3), Float32(2/3),
                  Float32(-.5), Float32(0.001)]
        sines = [math.sin(x * Float32(math.pi/2)) for x in inputs]
        cosines = [math.cos(x * Float32(math.pi/2)) for x in inputs]
        outputs = zip(sines, cosines)
        self.run_test(iter(inputs), outputs=iter(outputs))


if __name__ == "__main__":
    unittest.main()

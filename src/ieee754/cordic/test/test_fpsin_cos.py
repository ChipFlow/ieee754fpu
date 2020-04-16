from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Delay
from nmigen.test.utils import FHDLTestCase

from ieee754.cordic.fpsin_cos import CORDIC
from ieee754.fpcommon.fpbase import FPNumBaseRecord
from python_sin_cos import run_cordic
from sfpy import Float16, Float32
import unittest
import math
import random


class SinCosTestCase(FHDLTestCase):
    def run_test(self, zin=0, fracbits=8, expected_sin=0, expected_cos=0):

        m = Module()

        m.submodules.dut = dut = CORDIC(32)
        z = Signal(dut.z0.width)
        start = Signal()

        sin = Signal(dut.sin.shape())
        cos = Signal(dut.cos.shape())
        ready = Signal()

        m.d.comb += [
            dut.z0.eq(z),
            dut.start.eq(start),
            sin.eq(dut.sin),
            cos.eq(dut.cos),
            ready.eq(dut.ready)]

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            yield z.eq(zin.get_bits())
            yield start.eq(1)

            yield
            yield start.eq(0)
            yield
            for i in range(fracbits * 3):
                rdy = yield ready
                yield

        sim.add_sync_process(process)
        with sim.write_vcd("fpsin_cos.vcd", "fpsin_cos.gtkw", traces=[
                 cos, sin, ready, start]):
            sim.run()

    def run_test_assert(self, z, fracbits=8):
        self.run_test(zin=z, fracbits=fracbits)

    def test_1(self):
        x = Float32(1.0)
        self.run_test_assert(x)

    # def test_neg(self):
    #     self.run_test_assert(-6)

    # def test_rand(self):
    #     fracbits = 16
    #     M = (1 << fracbits)
    #     ZMAX = int(round(M * math.pi/2))
    #     for i in range(500):
    #         z = random.randrange(-ZMAX, ZMAX-1)
    #         self.run_test_assert(z, fracbits=fracbits)


if __name__ == "__main__":
    unittest.main()

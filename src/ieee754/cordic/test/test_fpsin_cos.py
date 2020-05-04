from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Delay
from nmigen.test.utils import FHDLTestCase

from ieee754.cordic.fpsin_cos import CORDIC
from ieee754.fpcommon.fpbase import FPNumBaseRecord
from python_sin_cos import run_cordic
from sfpy import Float16, Float32, Float64
import unittest
import math
import random

float_class_for_bits = {64: Float64,
                        32: Float32,
                        16: Float16}


class SinCosTestCase(FHDLTestCase):
    def run_test(self, zin=0, bits=64, expected_sin=0, expected_cos=0):

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
            asserted = False
            yield z.eq(zin.get_bits())
            yield start.eq(1)

            yield
            yield start.eq(0)
            yield
            for i in range(dut.fracbits+1):
                rdy = yield ready
                zo = yield dut.z_out
                if rdy and not asserted:
                    frac = self.get_frac(zo, dut.z_out.width - 2)
                    print(f"{zo:x} {frac}", end=' ')
                    #self.assertEqual(str(frac), zin.__str__())
                    asserted = True

                    real_sin = yield dut.sin
                    real_sin = self.get_frac(real_sin, dut.sin.width - 2)
                    diff = abs(real_sin - expected_sin)
                    print(f"{real_sin} {expected_sin} {diff}", end=' ')
                    #self.assertTrue(diff < 0.001)
                    real_cos = yield dut.cos
                    real_cos = self.get_frac(real_cos, dut.cos.width - 2)
                    diff = abs(real_cos - expected_cos)
                    print(f"{real_cos} {expected_cos} {diff}")
                    #self.assertTrue(diff < 0.001)

                yield

        sim.add_sync_process(process)
        with sim.write_vcd("fpsin_cos.vcd", "fpsin_cos.gtkw", traces=[
                 cos, sin, ready, start]):
            sim.run()

    def run_test_assert(self, z, bits=64):
        kls = float_class_for_bits[bits]
        zpi = z * kls(math.pi/2)
        e_sin = math.sin(zpi)
        e_cos = math.cos(zpi)
        self.run_test(zin=z, expected_sin=e_sin,
                      expected_cos=e_cos)

    def test_1(self):
        x = Float64(1.0)
        self.run_test_assert(x)

    def test_pi_4(self):
        x = Float32(1/2)
        self.run_test_assert(x, bits=32)

    def test_rand(self):
        for i in range(10000):
            z = 2*i/10000 - 1
            f = Float64(z)
            self.run_test_assert(f)

    def get_frac(self, value, bits):
        return value/(1 << bits)

if __name__ == "__main__":
    unittest.main()

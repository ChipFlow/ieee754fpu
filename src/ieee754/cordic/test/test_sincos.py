from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Delay
from nmigen.test.utils import FHDLTestCase

from ieee754.cordic.sin_cos import CORDIC
from python_sin_cos import run_cordic
import unittest
import math
import random

class SinCosTestCase(FHDLTestCase):
    def run_test(self, zin=0, fracbits=8, expected_sin=0, expected_cos=0):

        m = Module()

        m.submodules.dut = dut = CORDIC(fracbits)
        z = Signal(dut.z0.shape())
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
            yield z.eq(zin)
            yield start.eq(1)

            yield
            yield start.eq(0)
            yield
            for i in range(10):
                rdy = yield ready
                if rdy == 1:
                    result = yield sin
                    msg = "sin: {}, expected {}".format(result, expected_sin)
                    assert result == expected_sin, msg
                    result = yield cos
                    msg = "cos: {}, expected {}".format(result, expected_cos)
                    assert result == expected_cos, msg
                else:
                    yield

        sim.add_sync_process(process)
        with sim.write_vcd("sin_cos.vcd", "sin_cos.gtkw", traces=[
                z, cos, sin, ready, start]):
            sim.run()

    def run_test_assert(self, z, fracbits=8):
        (sin, cos) = run_cordic(z, fracbits=8, log=False)
        self.run_test(zin=z, fracbits=8,
                      expected_sin=sin, expected_cos=cos)
    def test_0(self):
        self.run_test_assert(0)
    def test_rand(self):
        fracbits = 8
        M = (1 << fracbits)
        ZMAX = int(round(M * math.pi/2))
        for i in range(100):
            z = random.randrange(-ZMAX, ZMAX-1)
            self.run_test_assert(z, fracbits=fracbits)
            
        

if __name__ == "__main__":
    unittest.main()

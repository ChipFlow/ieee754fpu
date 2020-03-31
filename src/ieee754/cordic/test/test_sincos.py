from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Delay
from nmigen.test.utils import FHDLTestCase

from ieee754.cordic.sin_cos import CORDIC
import unittest

class SinCosTestCase(FHDLTestCase):
    def test_sincos(self):
        m = Module()

        fracbits = 8

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
            for i in range(10):
                yield
        sim.add_sync_process(process)
        with sim.write_vcd("sin_cos.vcd", "sin_cos.gtkw", traces=[
                z, cos, sin, ready, start]):
            sim.run()

if __name__ == "__main__":
    unittest.main()

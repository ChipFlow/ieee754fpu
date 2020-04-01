from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Delay
from nmigen.test.utils import FHDLTestCase

from ieee754.cordic.sin_cos_pipeline import CordicBasePipe
from ieee754.cordic.pipe_data import CordicPipeSpec
from python_sin_cos import run_cordic
import unittest


class SinCosTestCase(FHDLTestCase):
    def run_test(self, zin=0, fracbits=8, expected_sin=0, expected_cos=0):
        m = Module()
        pspec = CordicPipeSpec(fracbits=fracbits)
        m.submodules.dut = dut = CordicBasePipe(pspec)

        z = Signal(dut.p.data_i.z0.shape())
        x = Signal(dut.n.data_o.x.shape())
        y = Signal(dut.n.data_o.y.shape())

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def process():
            yield z.eq(zin)
            for i in range(10):
                yield
        sim.add_sync_process(process)
        with sim.write_vcd("pipeline.vcd", "pipeline.gtkw", traces=[
                z, x, y]):
            sim.run()

    def run_test_assert(self, z, fracbits=8):
        (sin, cos) = run_cordic(z, fracbits=fracbits, log=False)
        self.run_test(zin=z, fracbits=fracbits,
                      expected_sin=sin, expected_cos=cos)

    def test_0(self):
        self.run_test_assert(0)


if __name__ == "__main__":
    unittest.main()

from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Passive
from nmigen.test.utils import FHDLTestCase

from ieee754.cordic.sin_cos_pipeline import CordicBasePipe
from ieee754.cordic.pipe_data import CordicPipeSpec
from python_sin_cos import run_cordic
import unittest
import math
import random


class SinCosTestCase(FHDLTestCase):
    def run_test(self, inputs, outputs, fracbits=8):
        m = Module()
        pspec = CordicPipeSpec(fracbits=fracbits)
        m.submodules.dut = dut = CordicBasePipe(pspec)

        z = Signal(dut.p.data_i.z0.shape())
        z_valid = Signal()
        ready = Signal()
        x = Signal(dut.n.data_o.x.shape())
        y = Signal(dut.n.data_o.y.shape())

        m.d.comb += [
            dut.p.data_i.z0.eq(z),
            dut.p.valid_i.eq(z_valid),
            dut.n.ready_i.eq(ready),
            x.eq(dut.n.data_o.x),
            y.eq(dut.n.data_o.y)]

        sim = Simulator(m)
        sim.add_clock(1e-6)

        def writer_process():
            yield Passive()
            for val in inputs:
                yield z.eq(val)
                yield z_valid.eq(1)
                yield ready.eq(1)
                yield

        def reader_process():
            while True:
                yield
                vld = yield dut.n.valid_o
                if vld:
                    try:
                        (sin, cos) = outputs.__next__()
                        result = yield x
                        msg = "cos: {}, expected {}".format(result, cos)
                        assert result == cos, msg
                        result = yield y
                        msg = "sin: {}, expected {}".format(result, sin)
                        assert result == sin, msg

                    except StopIteration:
                        break

        sim.add_sync_process(writer_process)
        sim.add_sync_process(reader_process)
        with sim.write_vcd("pipeline.vcd", "pipeline.gtkw", traces=[
                z, x, y]):
            sim.run()

    def test_rand(self):
        fracbits = 16
        M = (1 << fracbits)
        ZMAX = int(round(M * math.pi/2))
        inputs = []
        outputs = []
        for i in range(50):
            z = random.randrange(-ZMAX, ZMAX-1)
            (sin, cos) = run_cordic(z, fracbits=fracbits, log=False)
            inputs.append(z)
            outputs.append((sin, cos))
        self.run_test(iter(inputs), iter(outputs), fracbits=fracbits)


if __name__ == "__main__":
    unittest.main()

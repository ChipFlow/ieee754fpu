from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Delay
from nmigen.test.utils import FHDLTestCase

from ieee754.cordic.clz import CLZ
import unittest
import math
import random


class CLZTestCase(FHDLTestCase):
    def run_test(self, inputs, width=8):

        m = Module()

        m.submodules.dut = dut = CLZ(width)
        sig_in = Signal.like(dut.sig_in)
        count = Signal.like(dut.lz)


        m.d.comb += [
            dut.sig_in.eq(sig_in),
            count.eq(dut.lz)]

        sim = Simulator(m)

        def process():
            for i in inputs:
                yield sig_in.eq(i)
                yield Delay(1e-6)
        sim.add_process(process)
        with sim.write_vcd("clz.vcd", "clz.gtkw", traces=[
                sig_in, count]):
            sim.run()

    def test_selected(self):
        inputs = [0, 15, 10, 127]
        self.run_test(iter(inputs), width=8)

    def test_non_power_2(self):
        inputs = [0, 128, 512]
        self.run_test(iter(inputs), width=10)


if __name__ == "__main__":
    unittest.main()

from nmigen import Module, Signal
from nmigen.back.pysim import Simulator, Delay, Settle
from nmigen.test.utils import FHDLTestCase
from ieee754.part_mul_add.partpoints import PartitionPoints

from ieee754.part_shift.part_shift_dynamic import \
    PartitionedDynamicShift

import unittest

class DynamicShiftTestCase(FHDLTestCase):
    def get_intervals(self, signal, points):
        start = 0
        interval = []
        keys = list(points.keys()) + [signal.width]
        for key in keys:
            end = key
            interval.append(signal[start:end])
            start = end
        return interval

    def test_dynamic(self):
        m = Module()
        comb = m.d.comb
        mwidth = 4
        width = 32
        step = int(width/mwidth)
        gates = Signal(mwidth-1)
        points = PartitionPoints()
        for i in range(mwidth-1):
            points[(i+1)*step] = gates[i]
        a = Signal(width)
        b = Signal(width)
        output = Signal(width)
        a_intervals = self.get_intervals(a, points)
        b_intervals = self.get_intervals(b, points)
        output_intervals = self.get_intervals(output, points)

        m.submodules.dut = dut = PartitionedDynamicShift(width, points)
        comb += [dut.a.eq(a),
                 dut.b.eq(b),
                 output.eq(dut.output)]

        sim = Simulator(m)
        def process():
            yield a.eq(0x01010101)
            yield b.eq(0x04030201)
            for i in range(1<<(mwidth-1)):
                yield gates.eq(i)
                yield Delay(1e-6)
                yield Settle()
            yield b.eq(0x0c0b0a09)
            for i in range(1<<(mwidth-1)):
                yield gates.eq(i)
                yield Delay(1e-6)
                yield Settle()
            yield gates.eq(1)
            yield Delay(1e-6)
            yield Settle()
            yield gates.eq(0)
            yield Delay(1e-6)
            yield Settle()


        sim.add_process(process)
        with sim.write_vcd("test.vcd", "test.gtkw", traces=[a,b,output]):
            sim.run()

if __name__ == "__main__":
    unittest.main()





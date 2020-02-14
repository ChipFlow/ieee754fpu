# Proof of correctness for partitioned dynamic shifter
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable, Mux, Cat
from nmigen.asserts import Assert, AnyConst
from nmigen.test.utils import FHDLTestCase
from nmigen.cli import rtlil

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_shift.part_shift_dynamic import \
    PartitionedDynamicShift
import unittest


# This defines a module to drive the device under test and assert
# properties about its outputs
class ShifterDriver(Elaboratable):
    def __init__(self):
        # inputs and outputs
        pass

    def get_intervals(self, signal, points):
        start = 0
        interval = []
        keys = list(points.keys()) + [signal.width]
        for key in keys:
            end = key
            interval.append(signal[start:end])
            start = end
        return interval

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        width = 32
        mwidth = 4

        # setup the inputs and outputs of the DUT as anyconst
        a = Signal(width)
        b = Signal(width)
        out = Signal(width)
        points = PartitionPoints()
        gates = Signal(mwidth-1)
        step = int(width/mwidth)
        for i in range(mwidth-1):
            points[(i+1)*step] = gates[i]
        print(points)

        comb += [a.eq(AnyConst(width)),
                 b.eq(AnyConst(width)),
                 gates.eq(AnyConst(mwidth-1))]

        m.submodules.dut = dut = PartitionedDynamicShift(width, points)

        a_intervals = self.get_intervals(a, points)
        b_intervals = self.get_intervals(b, points)
        out_intervals = self.get_intervals(out, points)

        comb += [dut.a.eq(a),
                 dut.b.eq(b),
                 out.eq(dut.output)]


        with m.Switch(points.as_sig()):
            with m.Case(0b000):
                comb += Assert(out == (a<<b[0:5]) & 0xffffffff)
            with m.Case(0b001):
                comb += Assert(out_intervals[0] ==
                               (a_intervals[0] << b_intervals[0][0:3]) & 0xff)
                comb += Assert(Cat(out_intervals[1:4]) ==
                               (Cat(a_intervals[1:4])
                                << b_intervals[1][0:5]) & 0xffffff)
            with m.Case(0b010):
                comb += Assert(Cat(out_intervals[0:2]) ==
                               (Cat(a_intervals[0:2])
                                << (b_intervals[0] & 0xf)) & 0xffff)
                comb += Assert(Cat(out_intervals[2:4]) ==
                               (Cat(a_intervals[2:4])
                                << (b_intervals[2] & 0xf)) & 0xffff)
            with m.Case(0b011):
                comb += Assert(out_intervals[0] ==
                               (a_intervals[0] << b_intervals[0][0:3]) & 0xff)
                comb += Assert(out_intervals[1] ==
                               (a_intervals[1] << b_intervals[1][0:3]) & 0xff)
                comb += Assert(Cat(out_intervals[2:4]) ==
                               (Cat(a_intervals[2:4])
                                << b_intervals[2][0:4]) & 0xffff)
            with m.Case(0b100):
                comb += Assert(Cat(out_intervals[0:3]) ==
                               (Cat(a_intervals[0:3])
                                << b_intervals[0][0:5]) & 0xffffff)
                comb += Assert(out_intervals[3] ==
                               (a_intervals[3] << b_intervals[3][0:3]) & 0xff)
            with m.Case(0b101):
                comb += Assert(out_intervals[0] ==
                               (a_intervals[0] << b_intervals[0][0:3]) & 0xff)
                comb += Assert(Cat(out_intervals[1:3]) ==
                               (Cat(a_intervals[1:3])
                                << b_intervals[1][0:4]) & 0xffff)
                comb += Assert(out_intervals[3] ==
                               (a_intervals[3] << b_intervals[3][0:3]) & 0xff)
            with m.Case(0b110):
                comb += Assert(Cat(out_intervals[0:2]) ==
                               (Cat(a_intervals[0:2])
                                << b_intervals[0][0:4]) & 0xffff)
                comb += Assert(out_intervals[2] ==
                               (a_intervals[2] << b_intervals[2][0:3]) & 0xff)
                comb += Assert(out_intervals[3] ==
                               (a_intervals[3] << b_intervals[3][0:3]) & 0xff)
            with m.Case(0b111):
                for i, o in enumerate(out_intervals):
                    comb += Assert(o ==
                                   (a_intervals[i] << b_intervals[i][0:3])
                                   & 0xff)

        return m

class PartitionedDynamicShiftTestCase(FHDLTestCase):
    def test_shift(self):
        module = ShifterDriver()
        self.assertFormal(module, mode="bmc", depth=4)

    def test_ilang(self):
        width = 64
        mwidth = 8
        gates = Signal(mwidth-1)
        points = PartitionPoints()
        step = int(width/mwidth)
        for i in range(mwidth-1):
            points[(i+1)*step] = gates[i]
        print(points)
        dut = PartitionedDynamicShift(width, points)
        vl = rtlil.convert(dut, ports=[gates, dut.a, dut.b, dut.output])
        with open("dynamic_shift.il", "w") as f:
            f.write(vl)


if __name__ == "__main__":
    unittest.main()

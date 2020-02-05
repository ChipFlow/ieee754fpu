# Proof of correctness for partitioned equals module
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable, Mux
from nmigen.asserts import Assert, AnyConst, Assume
from nmigen.test.utils import FHDLTestCase
from nmigen.cli import rtlil

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_cmp.equal_ortree import PartitionedEq
import unittest


# This defines a module to drive the device under test and assert
# properties about its outputs
class EqualsDriver(Elaboratable):
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
        points = PartitionPoints()
        gates = Signal(mwidth-1)
        for i in range(mwidth-1):
            points[i*4+4] = gates[i]
        out = Signal(mwidth)

        comb += [a.eq(AnyConst(width)),
                 b.eq(AnyConst(width)),
                 gates.eq(AnyConst(mwidth-1))]

        m.submodules.dut = dut = PartitionedEq(width, points)

        a_intervals = self.get_intervals(a, points)
        b_intervals = self.get_intervals(b, points)

        with m.Switch(gates):
            with m.Case(0b000):
                comb += Assert(out == (a == b))
            with m.Case(0b001):
                comb += Assert(out[1] == ((a_intervals[1] == b_intervals[1]) &
                                          (a_intervals[2] == b_intervals[2]) &
                                          (a_intervals[3] == b_intervals[3])))
                comb += Assert(out[0] == (a_intervals[0] == b_intervals[0]))
            with m.Case(0b010):
                comb += Assert(out[2] == ((a_intervals[2] == b_intervals[2]) &
                                          (a_intervals[3] == b_intervals[3])))
                comb += Assert(out[0] == ((a_intervals[0] == b_intervals[0]) &
                                          (a_intervals[1] == b_intervals[1])))
            with m.Case(0b011):
                comb += Assert(out[2] == ((a_intervals[2] == b_intervals[2]) &
                                          (a_intervals[3] == b_intervals[3])))
                comb += Assert(out[0] == (a_intervals[0] == b_intervals[0]))
                comb += Assert(out[1] == (a_intervals[1] == b_intervals[1]))
            with m.Case(0b100):
                comb += Assert(out[0] == ((a_intervals[0] == b_intervals[0]) &
                                          (a_intervals[1] == b_intervals[1]) &
                                          (a_intervals[2] == b_intervals[2])))
                comb += Assert(out[3] == (a_intervals[3] == b_intervals[3]))
            with m.Case(0b101):
                comb += Assert(out[1] == ((a_intervals[1] == b_intervals[1]) &
                                          (a_intervals[2] == b_intervals[2])))
                comb += Assert(out[3] == (a_intervals[3] == b_intervals[3]))
                comb += Assert(out[0] == (a_intervals[0] == b_intervals[0]))
            with m.Case(0b110):
                comb += Assert(out[0] == ((a_intervals[0] == b_intervals[0]) &
                                          (a_intervals[1] == b_intervals[1])))
                comb += Assert(out[3] == (a_intervals[3] == b_intervals[3]))
                comb += Assert(out[2] == (a_intervals[2] == b_intervals[2]))
            with m.Case(0b111):
                for i in range(mwidth-1):
                    comb += Assert(out[i] == (a_intervals[i] == b_intervals[i]))



        comb += [dut.a.eq(a),
                 dut.b.eq(b),
                 out.eq(dut.output)]
        return m

class PartitionedEqTestCase(FHDLTestCase):
    def test_eq(self):
        module = EqualsDriver()
        self.assertFormal(module, mode="bmc", depth=4)

if __name__ == "__main__":
    unittest.main()


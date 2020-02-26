# Proof of correctness for partitioned scalar shifter
# Copyright (C) 2020 Michael Nolan <mtnolan2640@gmail.com>

from nmigen import Module, Signal, Elaboratable, Mux, Cat
from nmigen.asserts import Assert, AnyConst, Assume
from nmigen.test.utils import FHDLTestCase
from nmigen.cli import rtlil

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_shift.part_shift_scalar import PartitionedScalarShift
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
        width = 24
        shifterwidth = 5
        mwidth = 3

        # setup the inputs and outputs of the DUT as anyconst
        data = Signal(width)
        out = Signal(width)
        shifter = Signal(shifterwidth)
        points = PartitionPoints()
        gates = Signal(mwidth-1)
        shift_right = Signal()
        step = int(width/mwidth)
        for i in range(mwidth-1):
            points[(i+1)*step] = gates[i]
        print(points)

        comb += [data.eq(AnyConst(width)),
                 shift_right.eq(AnyConst(1)),
                 shifter.eq(AnyConst(shifterwidth)),
                 gates.eq(AnyConst(mwidth-1))]

        m.submodules.dut = dut = PartitionedScalarShift(width, points)

        data_intervals = self.get_intervals(data, points)
        out_intervals = self.get_intervals(out, points)

        comb += [dut.data.eq(data),
                 dut.shifter.eq(shifter),
                 dut.shift_right.eq(shift_right),
                 out.eq(dut.output)]

        expected = Signal(width)

        with m.If(shift_right == 0):
            with m.Switch(points.as_sig()):
                with m.Case(0b00):
                    comb += Assert(
                        out[0:24] == (data[0:24] << (shifter & 0x1f)) &
                        0xffffff)

                with m.Case(0b01):
                    comb += Assert(out[0:8] ==
                                (data[0:8] << (shifter & 0x7)) & 0xFF)
                    comb += Assert(out[8:24] ==
                                (data[8:24] << (shifter & 0xf)) & 0xffff)

                with m.Case(0b10):
                    comb += Assert(out[16:24] ==
                                (data[16:24] << (shifter & 0x7)) & 0xff)
                    comb += Assert(out[0:16] ==
                                (data[0:16] << (shifter & 0xf)) & 0xffff)

                with m.Case(0b11):
                    comb += Assert(out[0:8] ==
                                (data[0:8] << (shifter & 0x7)) & 0xFF)
                    comb += Assert(out[8:16] ==
                                (data[8:16] << (shifter & 0x7)) & 0xff)
                    comb += Assert(out[16:24] ==
                                (data[16:24] << (shifter & 0x7)) & 0xff)
        with m.Else():
            with m.Switch(points.as_sig()):
                with m.Case(0b00):
                    comb += Assert(
                        out[0:24] == (data[0:24] >> (shifter & 0x1f)) &
                        0xffffff)

                with m.Case(0b01):
                    comb += Assert(out[0:8] ==
                                (data[0:8] >> (shifter & 0x7)) & 0xFF)
                    comb += Assert(out[8:24] ==
                                (data[8:24] >> (shifter & 0xf)) & 0xffff)

                with m.Case(0b10):
                    comb += Assert(out[16:24] ==
                                (data[16:24] >> (shifter & 0x7)) & 0xff)
                    comb += Assert(out[0:16] ==
                                (data[0:16] >> (shifter & 0xf)) & 0xffff)

                with m.Case(0b11):
                    comb += Assert(out[0:8] ==
                                (data[0:8] >> (shifter & 0x7)) & 0xFF)
                    comb += Assert(out[8:16] ==
                                (data[8:16] >> (shifter & 0x7)) & 0xff)
                    comb += Assert(out[16:24] ==
                                (data[16:24] >> (shifter & 0x7)) & 0xff)
        return m

class PartitionedScalarShiftTestCase(FHDLTestCase):
    def test_shift(self):
        module = ShifterDriver()
        self.assertFormal(module, mode="bmc", depth=4)
    def test_ilang(self):
        width = 24
        mwidth = 3
        gates = Signal(mwidth-1)
        points = PartitionPoints()
        step = int(width/mwidth)
        for i in range(mwidth-1):
            points[(i+1)*step] = gates[i]
        print(points)
        dut = PartitionedScalarShift(width, points)
        vl = rtlil.convert(dut, ports=[gates, dut.data,
                                       dut.shifter,
                                       dut.output])
        with open("scalar_shift.il", "w") as f:
            f.write(vl)

if __name__ == "__main__":
    unittest.main()

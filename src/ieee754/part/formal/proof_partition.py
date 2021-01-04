"""Formal verification of partitioned operations

The approach is to take an arbitrary partition, by choosing its start point
and size at random. Use ``Assume`` to ensure it is a whole unbroken partition
(start and end points are one, with only zeros in between). Shift inputs and
outputs down to zero. Loop over all possible partition sizes and, if it's the
right size, compute the expected value, compare with the result, and assert.

We are turning the for-loops around (on their head), such that we start from
the *lengths* (and positions) and perform the ``Assume`` on the resultant
partition bits.

In other words, we have patterns as follows (assuming 32-bit words)::

  8-bit offsets 0,1,2,3
  16-bit offsets 0,1,2
  24-bit offsets 0,1
  32-bit

* for 8-bit the partition bit is 1 and the previous is also 1

* for 16-bit the partition bit at the offset must be 0 and be surrounded by 1

* for 24-bit the partition bits at the offset and at offset+1 must be 0 and at
  offset+2 and offset-1 must be 1

* for 32-bit all 3 bits must be 0 and be surrounded by 1 (guard bits are added
  at each end for this purpose)

"""

import os
import unittest

from nmigen import Elaboratable, Signal, Module, Const
from nmigen.asserts import Assert, Cover

from nmutil.formaltest import FHDLTestCase
from nmutil.gtkw import write_gtkw

from ieee754.part_mul_add.partpoints import PartitionPoints


class PartitionedPattern(Elaboratable):
    """ Generate a unique pattern, depending on partition size.

    * 1-byte partitions: 0x11
    * 2-byte partitions: 0x21 0x22
    * 3-byte partitions: 0x31 0x32 0x33

    And so on.

    Useful as a test vector for testing the formal prover

    """
    def __init__(self, width, partition_points):
        self.width = width
        self.partition_points = PartitionPoints(partition_points)
        self.mwidth = len(self.partition_points)+1
        self.output = Signal(self.width, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # Add a guard bit at each end
        positions = [0] + list(self.partition_points.keys()) + [self.width]
        gates = [Const(1)] + list(self.partition_points.values()) + [Const(1)]
        # Begin counting at one
        last_start = positions[0]
        last_end = positions[1]
        last_middle = (last_start+last_end)//2
        comb += self.output[last_start:last_middle].eq(1)
        # Build an incrementing cascade
        for i in range(1, self.mwidth):
            start = positions[i]
            end = positions[i+1]
            middle = (start + end) // 2
            # Propagate from the previous byte, adding one to it.
            with m.If(~gates[i]):
                comb += self.output[start:middle].eq(
                    self.output[last_start:last_middle] + 1)
            with m.Else():
                # ... unless it's a partition boundary. If so, start again.
                comb += self.output[start:middle].eq(1)
            last_start = start
            last_middle = middle
        # Mirror the nibbles on the last byte
        last_start = positions[-2]
        last_end = positions[-1]
        last_middle = (last_start+last_end)//2
        comb += self.output[last_middle:last_end].eq(
            self.output[last_start:last_middle])
        for i in range(self.mwidth, 0, -1):
            start = positions[i-1]
            end = positions[i]
            middle = (start + end) // 2
            # Propagate from the previous byte.
            with m.If(~gates[i]):
                comb += self.output[middle:end].eq(
                    self.output[last_middle:last_end])
            with m.Else():
                # ... unless it's a partition boundary.
                # If so, mirror the nibbles again.
                comb += self.output[middle:end].eq(
                    self.output[start:middle])
            last_middle = middle
            last_end = end

        return m


# This defines a module to drive the device under test and assert
# properties about its outputs
class Driver(Elaboratable):
    def __init__(self):
        # inputs and outputs
        pass

    @staticmethod
    def elaborate(_):
        m = Module()
        comb = m.d.comb
        width = 64
        mwidth = 8
        # Setup partition points and gates
        points = PartitionPoints()
        gates = Signal(mwidth-1)
        step = int(width/mwidth)
        for i in range(mwidth-1):
            points[(i+1)*step] = gates[i]
        # Instantiate the partitioned pattern producer
        m.submodules.dut = dut = PartitionedPattern(width, points)
        # Directly check some cases
        with m.If(gates == 0):
            comb += Assert(dut.output == 0x_88_87_86_85_84_83_82_81)
        with m.If(gates == 0b1100101):
            comb += Assert(dut.output == 0x_11_11_33_32_31_22_21_11)
        with m.If(gates == 0b0001000):
            comb += Assert(dut.output == 0x_44_43_42_41_44_43_42_41)
        with m.If(gates == 0b0100001):
            comb += Assert(dut.output == 0x_22_21_55_54_53_52_51_11)
        with m.If(gates == 0b1000001):
            comb += Assert(dut.output == 0x_11_66_65_64_63_62_61_11)
        with m.If(gates == 0b0000001):
            comb += Assert(dut.output == 0x_77_76_75_74_73_72_71_11)
        # Make it interesting, by having three partitions
        comb += Cover(sum(gates) == 3)
        return m


class PartitionTestCase(FHDLTestCase):
    def test_formal(self):
        traces = ['output[63:0]', 'gates[6:0]']
        write_gtkw(
            'test_formal_cover.gtkw',
            os.path.dirname(__file__) +
            '/proof_partition_formal/engine_0/trace0.vcd',
            traces,
            module='top.dut',
            zoom="formal"
        )
        write_gtkw(
            'test_formal_bmc.gtkw',
            os.path.dirname(__file__) +
            '/proof_partition_formal/engine_0/trace.vcd',
            traces,
            module='top.dut',
            zoom="formal"
        )
        module = Driver()
        self.assertFormal(module, mode="bmc", depth=1)
        self.assertFormal(module, mode="cover", depth=1)


if __name__ == '__main__':
    unittest.main()

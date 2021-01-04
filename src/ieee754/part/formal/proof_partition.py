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
        comb += self.output[last_start:last_end].eq(1)
        # Build an incrementing cascade
        for i in range(1, self.mwidth):
            start = positions[i]
            end = positions[i+1]
            # Propagate from the previous byte, adding one to it
            comb += self.output[start:end].eq(
                self.output[last_start:last_end] + 1)
            last_start = start
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
        sync = m.d.sync
        width = 64
        mwidth = 8
        out = Signal(width)
        # Setup partition points and gates
        points = PartitionPoints()
        gates = Signal(mwidth-1)
        step = int(width/mwidth)
        for i in range(mwidth-1):
            points[(i+1)*step] = gates[i]
        # Instantiate the partitioned pattern producer
        m.submodules.dut = dut = PartitionedPattern(width, points)
        # Directly check some cases
        comb += Assert(dut.output == 0x0807060504030201)
        comb += Cover(1)
        return m


class PartitionTestCase(FHDLTestCase):
    def test_formal(self):
        traces = ['output[63:0]']
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

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
from nmigen.hdl.ast import Assume

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
        # Choose a partition offset and width at random.
        p_offset = Signal(range(mwidth))
        p_width = Signal(range(mwidth+1))
        p_finish = Signal(range(mwidth+1))
        comb += p_finish.eq(p_offset + p_width)
        # Partition must not be empty, and fit within the signal.
        comb += Assume(p_width != 0)
        comb += Assume(p_offset + p_width <= mwidth)

        # Build the corresponding partition
        # Use Assume to constraint the pattern to conform to the given offset
        # and width. For each gate bit it is:
        # 1) one, if on the partition boundary
        # 2) zero, if it's inside the partition
        # 3) don't care, otherwise
        p_gates = Signal(mwidth+1)
        for i in range(mwidth+1):
            with m.If(i == p_offset):
                # Partitions begin with 1
                comb += Assume(p_gates[i] == 1)
            with m.If((i > p_offset) & (i < p_finish)):
                # The interior are all zeros
                comb += Assume(p_gates[i] == 0)
            with m.If(i == p_finish):
                # End with 1 again
                comb += Assume(p_gates[i] == 1)
        # Check some possible partitions generating a given pattern
        with m.If(p_gates == 0b0100110):
            comb += Assert(((p_offset == 1) & (p_width == 1)) |
                           ((p_offset == 2) & (p_width == 3)))
        # Remove guard bits at each end and assign to the DUT gates
        comb += gates.eq(p_gates[1:])
        # Generate shifted down outputs:
        p_output = Signal(width)
        positions = [0] + list(points.keys()) + [width]
        for i in range(mwidth):
            with m.If(p_offset == i):
                comb += p_output.eq(dut.output[positions[i]:])
        # Some checks on the shifted down output, irrespective of offset:
        with m.If(p_width == 2):
            comb += Assert(p_output[:16] == 0x_22_21)
        with m.If(p_width == 4):
            comb += Assert(p_output[:32] == 0x_44_43_42_41)
        # test zero shift
        with m.If(p_offset == 0):
            comb += Assert(p_output == dut.output)
        # Output an example.
        # Make it interesting, by having four partitions.
        # Make the selected partition not start at the very beginning.
        comb += Cover((sum(gates) == 3) & (p_offset != 0) & (p_width == 3))
        # Generate and check expected values for all possible partition sizes.
        # Here, we assume partition sizes are multiple of the smaller size.
        for w in range(1, mwidth+1):
            with m.If(p_width == w):
                # calculate the expected output, for the given bit width
                bit_width = w * step
                expected = Signal(bit_width, name=f"expected_{w}")
                for b in range(w):
                    # lower nibble is the position
                    comb += expected[b*8:b*8+4].eq(b+1)
                    # upper nibble is the partition width
                    comb += expected[b*8+4:b*8+8].eq(w)
                # truncate the output, compare and assert
                comb += Assert(p_output[:bit_width] == expected)
        return m


class GateGenerator(Elaboratable):
    """Produces partition gates at random

    `p_offset`, `p_width` and `p_finish` describe the selected partition
    """
    def __init__(self, mwidth):
        self.mwidth = mwidth
        """Number of partitions"""
        self.gates = Signal(mwidth-1)
        """Generated partition gates"""
        self.p_offset = Signal(range(mwidth))
        """Generated partition start point"""
        self.p_width = Signal(range(mwidth+1))
        """Generated partition width"""
        self.p_finish = Signal(range(mwidth+1))
        """Generated partition end point"""

    def elaborate(self, _):
        m = Module()
        comb = m.d.comb
        mwidth = self.mwidth
        gates = self.gates
        p_offset = self.p_offset
        p_width = self.p_width
        p_finish = self.p_finish
        comb += p_finish.eq(p_offset + p_width)
        # Partition must not be empty, and fit within the signal.
        comb += Assume(p_width != 0)
        comb += Assume(p_offset + p_width <= mwidth)

        # Build the corresponding partition
        # Use Assume to constraint the pattern to conform to the given offset
        # and width. For each gate bit it is:
        # 1) one, if on the partition boundary
        # 2) zero, if it's inside the partition
        # 3) don't care, otherwise
        p_gates = Signal(mwidth+1)
        for i in range(mwidth+1):
            with m.If(i == p_offset):
                # Partitions begin with 1
                comb += Assume(p_gates[i] == 1)
            with m.If((i > p_offset) & (i < p_finish)):
                # The interior are all zeros
                comb += Assume(p_gates[i] == 0)
            with m.If(i == p_finish):
                # End with 1 again
                comb += Assume(p_gates[i] == 1)
        # Remove guard bits at each end, before assigning to the output gates
        comb += gates.eq(p_gates[1:])
        return m


class GeneratorDriver(Elaboratable):
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
        # Instantiate the partitioned pattern producer and the DUT
        m.submodules.dut = dut = PartitionedPattern(width, points)
        m.submodules.gen = gen = GateGenerator(mwidth)
        comb += gates.eq(gen.gates)
        # Generate shifted down outputs
        p_offset = gen.p_offset
        p_width = gen.p_width
        p_output = Signal(width)
        for i in range(mwidth):
            with m.If(p_offset == i):
                comb += p_output.eq(dut.output[i*step:])
        # Generate and check expected values for all possible partition sizes.
        for w in range(1, mwidth+1):
            with m.If(p_width == w):
                # calculate the expected output, for the given bit width
                bit_width = w * step
                expected = Signal(bit_width, name=f"expected_{w}")
                for b in range(w):
                    # lower nibble is the position
                    comb += expected[b*8:b*8+4].eq(b+1)
                    # upper nibble is the partition width
                    comb += expected[b*8+4:b*8+8].eq(w)
                # truncate the output, compare and assert
                comb += Assert(p_output[:bit_width] == expected)
        # Output an example.
        # Make it interesting, by having four partitions.
        # Make the selected partition not start at the very beginning.
        comb += Cover((sum(gates) == 3) & (p_offset != 0) & (p_width == 3))
        return m


class PartitionTestCase(FHDLTestCase):
    def test_formal(self):
        traces = [
            ('p_offset[2:0]', {'base': 'dec'}),
            ('p_width[3:0]', {'base': 'dec'}),
            ('p_finish[3:0]', {'base': 'dec'}),
            ('p_gates[8:0]', {'base': 'bin'}),
            ('dut', {'submodule': 'dut'}, [
                ('gates[6:0]', {'base': 'bin'}),
                'output[63:0]']),
            'p_output[63:0]', 'expected_3[21:0]']
        write_gtkw(
            'proof_partition_cover.gtkw',
            os.path.dirname(__file__) +
            '/proof_partition_formal/engine_0/trace0.vcd',
            traces,
            module='top',
            zoom=-3
        )
        write_gtkw(
            'proof_partition_bmc.gtkw',
            os.path.dirname(__file__) +
            '/proof_partition_formal/engine_0/trace.vcd',
            traces,
            module='top',
            zoom=-3
        )
        module = Driver()
        self.assertFormal(module, mode="bmc", depth=1)
        self.assertFormal(module, mode="cover", depth=1)

    def test_generator(self):
        traces = [
            ('p_offset[2:0]', {'base': 'dec'}),
            ('p_width[3:0]', {'base': 'dec'}),
            ('p_finish[3:0]', {'base': 'dec'}),
            ('p_gates[8:0]', {'base': 'bin'}),
            ('dut', {'submodule': 'dut'}, [
                ('gates[6:0]', {'base': 'bin'}),
                'output[63:0]']),
            'p_output[63:0]', 'expected_3[21:0]']
        write_gtkw(
            'proof_partition_generator_cover.gtkw',
            os.path.dirname(__file__) +
            '/proof_partition_generator/engine_0/trace0.vcd',
            traces,
            module='top',
            zoom=-3
        )
        write_gtkw(
            'proof_partition_generator_bmc.gtkw',
            os.path.dirname(__file__) +
            '/proof_partition_generator/engine_0/trace.vcd',
            traces,
            module='top',
            zoom=-3
        )
        module = GeneratorDriver()
        self.assertFormal(module, mode="bmc", depth=1)
        self.assertFormal(module, mode="cover", depth=1)


if __name__ == '__main__':
    unittest.main()

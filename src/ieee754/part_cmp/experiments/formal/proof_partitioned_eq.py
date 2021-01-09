import os
import unittest

from nmigen import Elaboratable, Signal, Module
from nmigen.asserts import Assert, Cover

from nmutil.formaltest import FHDLTestCase
from nmutil.gtkw import write_gtkw

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part.formal.proof_partition import GateGenerator
from ieee754.part_cmp.experiments.equal_ortree import PartitionedEq


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
        # instantiate the DUT
        m.submodules.dut = dut = PartitionedEq(width, points)
        # instantiate the partitioned gate generator and connect the gates
        m.submodules.gen = gen = GateGenerator(mwidth)
        comb += gates.eq(gen.gates)
        p_offset = gen.p_offset
        p_width = gen.p_width
        # generate shifted down inputs and outputs
        p_output = Signal(mwidth)
        p_a = Signal(width)
        p_b = Signal(width)
        for pos in range(mwidth):
            with m.If(p_offset == pos):
                # TODO: post-process the output to fill the partition with
                # the LSB
                comb += p_output.eq(dut.output[pos:])
                comb += p_a.eq(dut.a[pos * step:])
                comb += p_b.eq(dut.b[pos * step:])
        # generate and check expected values for all possible partition sizes
        for w in range(1, mwidth+1):
            with m.If(p_width == w):
                # calculate the expected output, for the given bit width,
                # truncating the inputs to the partition size
                input_bit_width = w * step
                output_bit_width = w
                expected = Signal(output_bit_width, name=f"expected_{w}")
                # TODO: the expected result is all zeros or all ones
                comb += expected.eq(0)
                comb += expected[0].eq(
                    p_a[:input_bit_width] == p_b[:input_bit_width])
                # truncate the output, compare and assert
                comb += Assert(p_output[:output_bit_width] == expected)
        # output an example
        # make the selected partition not start at the very beginning
        comb += Cover((p_offset != 0) & (p_width == 3) & (dut.a != dut.b))
        return m


class PartitionedEqTestCase(FHDLTestCase):

    def test_formal(self):
        traces = [
            ('p_offset[2:0]', {'base': 'dec'}),
            ('p_width[3:0]', {'base': 'dec'}),
            ('p_gates[8:0]', {'base': 'bin'}),
            ('dut', {'submodule': 'dut'}, [
                ('gates[6:0]', {'base': 'bin'}),
                'a[63:0]', 'b[63:0]',
                ('output[7:0]', {'base': 'bin'})]),
            ('p_output[7:0]', {'base': 'bin'}),
            'expected_3']
        write_gtkw(
            'proof_partitioned_eq_cover.gtkw',
            os.path.dirname(__file__) +
            '/proof_partitioned_eq_formal/engine_0/trace0.vcd',
            traces,
            module='top',
            zoom=-3
        )
        write_gtkw(
            'proof_partitioned_eq_bmc.gtkw',
            os.path.dirname(__file__) +
            '/proof_partitioned_eq_formal/engine_0/trace.vcd',
            traces,
            module='top',
            zoom=-3
        )
        module = Driver()
        self.assertFormal(module, mode="bmc", depth=1)
        self.assertFormal(module, mode="cover", depth=1)


if __name__ == '__main__':
    unittest.main()

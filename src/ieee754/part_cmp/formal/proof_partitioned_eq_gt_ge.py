import os
import unittest

from nmigen import Elaboratable, Signal, Module, Repl
from nmigen.asserts import Assert, Cover

from nmutil.formaltest import FHDLTestCase
from nmutil.gtkw import write_gtkw

from ieee754.part.formal.proof_partition import GateGenerator, make_partitions
from ieee754.part_cmp.eq_gt_ge import PartitionedEqGtGe


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
        step = int(width/mwidth)
        points, gates = make_partitions(step, mwidth)
        # instantiate the DUT
        m.submodules.dut = dut = PartitionedEqGtGe(width, points)
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
                a = Signal(input_bit_width, name=f"a_{w}")
                b = Signal(input_bit_width, name=f"b_{w}")
                lsb = Signal(name=f"lsb_{w}")
                comb += a.eq(p_a[:input_bit_width])
                comb += b.eq(p_b[:input_bit_width])
                with m.If(dut.opcode == PartitionedEqGtGe.EQ):
                    comb += lsb.eq(a == b)
                with m.Elif(dut.opcode == PartitionedEqGtGe.GT):
                    comb += lsb.eq(a > b)
                with m.Elif(dut.opcode == PartitionedEqGtGe.GE):
                    comb += lsb.eq(a >= b)
                comb += expected.eq(Repl(lsb, output_bit_width))
                # truncate the output, compare and assert
                comb += Assert(p_output[:output_bit_width] == expected)
        # output an example
        # make the selected partition not start at the very beginning
        comb += Cover((p_offset != 0) & (p_width == 3) & (dut.a != dut.b))
        return m


class PartitionedEqTestCase(FHDLTestCase):

    def test_formal(self):
        style = {
            'dec': {'base': 'dec'},
            'bin': {'base': 'bin'}
        }
        traces = [
            ('p_offset[2:0]', 'dec'),
            ('p_width[3:0]', 'dec'),
            ('p_gates[8:0]', 'bin'),
            ('dut', {'submodule': 'dut'}, [
                ('gates[6:0]', 'bin'),
                'a[63:0]', 'b[63:0]',
                ('output[7:0]', 'bin')]),
            ('ripple', {'submodule': 'ripple'}, [
                ('output[7:0]', 'bin')]),
            ('p_output[7:0]', 'bin'),
            ('expected_3[2:0]', 'bin')]
        write_gtkw(
            'proof_partitioned_eq_gt_ge_cover.gtkw',
            os.path.dirname(__file__) +
            '/proof_partitioned_eq_gt_ge_formal/engine_0/trace0.vcd',
            traces, style,
            module='top',
            zoom=-3
        )
        write_gtkw(
            'proof_partitioned_eq_gt_ge_bmc.gtkw',
            os.path.dirname(__file__) +
            '/proof_partitioned_eq_gt_ge_formal/engine_0/trace.vcd',
            traces, style,
            module='top',
            zoom=-3
        )
        module = Driver()
        self.assertFormal(module, mode="bmc", depth=1)
        self.assertFormal(module, mode="cover", depth=1)


if __name__ == '__main__':
    unittest.main()

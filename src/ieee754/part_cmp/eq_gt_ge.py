# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "comparison" class, directly equivalent
to Signal.__eq__ except SIMD-partitionable

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/eq
* http://bugs.libre-riscv.org/show_bug.cgi?id=132
"""

from nmigen import Signal, Module, Elaboratable, Cat, C, Mux, Repl
from nmigen.back.pysim import Simulator, Delay, Settle
from nmigen.cli import main

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_cmp.experiments.gt_combiner import GTCombiner


class PartitionedEqGtGe(Elaboratable):
    EQ = C(0b00, 2)
    GT = C(0b01, 2)
    GE = C(0b10, 2)

    # Expansion of the partitioned equals module to handle Greater
    # Than and Greater than or Equal to. The function being evaluated
    # is selected by the opcode signal, where:
    # opcode 0x00 - EQ
    # opcode 0x01 - GT
    # opcode 0x02 - GE
    def __init__(self, width, partition_points):
        """Create a ``PartitionedEq`` operator
        """
        self.width = width
        self.a = Signal(width, reset_less=True)
        self.b = Signal(width, reset_less=True)
        self.opcode = Signal(2)
        self.partition_points = PartitionPoints(partition_points)
        self.mwidth = len(self.partition_points)+1
        self.output = Signal(self.mwidth, reset_less=True)
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        m.submodules.gtc = gtc = GTCombiner(self.mwidth)

        # make a series of "eqs" and "gts", splitting a and b into
        # partition chunks
        eqs = Signal(self.mwidth, reset_less=True)
        eql = []
        gts = Signal(self.mwidth, reset_less=True)
        gtl = []

        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            eql.append(self.a[start:end] == self.b[start:end])
            gtl.append(self.a[start:end] > self.b[start:end])
            start = end # for next time round loop
        comb += eqs.eq(Cat(*eql))
        comb += gts.eq(Cat(*gtl))

        # control the constant injected into the partition
        # next to a closed gate
        aux_input = Signal()
        # enable or disable the gt input for the gt partition combiner
        gt_en = Signal()

        with m.Switch(self.opcode):
            with m.Case(0b00):   # equals
                comb += aux_input.eq(1)
                comb += gt_en.eq(0)
            with m.Case(0b01):   # greater than
                comb += aux_input.eq(0)
                comb += gt_en.eq(1)
            with m.Case(0b10):   # greater than or equal to
                comb += aux_input.eq(1)
                comb += gt_en.eq(1)

        comb += gtc.gates.eq(self.partition_points.as_sig())
        comb += gtc.eqs.eq(eqs)
        comb += gtc.gts.eq(gts)
        comb += gtc.aux_input.eq(aux_input)
        comb += gtc.gt_en.eq(gt_en)
        comb += self.output.eq(gtc.outputs)

        return m

    def ports(self):
        return [self.a, self.b, self.opcode,
                self.partition_points.as_sig(),
                self.output]

if __name__ == "__main__":
    from ieee754.part_mul_add.partpoints import make_partition
    m = Module()
    mask = Signal(4)
    m.submodules.egg = egg = PartitionedEqGtGe(16, make_partition(mask, 16))

    sim = Simulator(m)

    def process():
        yield mask.eq(0b010)
        yield egg.a.eq(0xf000)
        yield egg.b.eq(0)
        yield Delay(1e-6)
        out = yield egg.output
        print ("out", bin(out))
        yield mask.eq(0b111)
        yield egg.a.eq(0x0000)
        yield egg.b.eq(0)
        yield Delay(1e-6)
        yield mask.eq(0b010)
        yield egg.a.eq(0x0000)
        yield egg.b.eq(0)
        yield Delay(1e-6)
        out = yield egg.output
        print ("out", bin(out))

    sim.add_process(process)
    with sim.write_vcd("eq_gt_ge.vcd", "eq_gt_ge.gtkw", traces=egg.ports()):
        sim.run()

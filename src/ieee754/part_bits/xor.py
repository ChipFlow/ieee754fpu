# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "xor" class, directly equivalent
to Signal.xor() except SIMD-partitionable

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/logicops
* http://bugs.libre-riscv.org/show_bug.cgi?id=176
"""

from nmigen import Signal, Module, Elaboratable, Cat, C, Mux, Repl
from nmigen.cli import main

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_cmp.experiments.eq_combiner import XORCombiner


class PartitionedXOR(Elaboratable):

    def __init__(self, width, partition_points):
        """Create a ``PartitionedXOR`` operator
        """
        self.width = width
        self.a = Signal(width, reset_less=True)
        self.partition_points = PartitionPoints(partition_points)
        self.mwidth = len(self.partition_points)+1
        self.output = Signal(self.mwidth, reset_less=True)
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        m.submodules.xorc = xorc = XORCombiner(self.mwidth)

        # make a series of "xor", splitting a and b into partition chunks
        xors = Signal(self.mwidth, reset_less=True)
        xorl = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            xorl.append(self.a[start:end].xor())
            start = end # for next time round loop
        comb += xors.eq(Cat(*xorl))

        # put the partial results through the combiner
        comb += xorc.gates.eq(self.partition_points.as_sig())
        comb += xorc.neqs.eq(xors)
        comb += self.output.eq(xorc.outputs)

        return m

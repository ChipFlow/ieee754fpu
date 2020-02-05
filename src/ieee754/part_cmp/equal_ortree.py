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
from nmigen.cli import main

from ieee754.part_mul_add.partpoints import PartitionPoints
from ieee754.part_cmp.experiments.eq_combiner import EQCombiner


class PartitionedEq(Elaboratable):

    def __init__(self, width, partition_points):
        """Create a ``PartitionedEq`` operator
        """
        self.width = width
        self.a = Signal(width, reset_less=True)
        self.b = Signal(width, reset_less=True)
        self.partition_points = PartitionPoints(partition_points)
        self.mwidth = len(self.partition_points)+1
        self.output = Signal(self.mwidth, reset_less=True)
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        m.submodules.eqc = eqc = EQCombiner(self.mwidth)

        # make a series of "not-eqs", splitting a and b into partition chunks
        nes = Signal(self.mwidth, reset_less=True)
        nel = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            nel.append(self.a[start:end] != self.b[start:end])
            start = end # for next time round loop
        comb += nes.eq(Cat(*nel))

        comb += eqc.gates.eq(self.partition_points.as_sig())
        comb += eqc.neqs.eq(nes)
        comb += self.output[0].eq(eqc.outputs)
        

        return m

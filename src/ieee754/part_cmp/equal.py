# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "comparison" class, directly equivalent
to Signal.__eq__ except SIMD-partitionable
"""

from nmigen import Signal, Module, Elaboratable, Cat, C, Mux, Repl
from nmigen.cli import main

from ieee754.part_mul_add.partpoints import PartitionPoints

class PartitionedEq(Elaboratable):

    def __init__(self, width, partition_points):
        """Create a ``PartitionedEq`` operator
        """
        self.width = width
        self.a = Signal(width, reset_less=True)
        self.b = Signal(width, reset_less=True)
        self.partition_points = PartitionPoints(partition_points)
        self.mwidth = len(self.partition_points)
        self.output = Signal(mwidth, reset_less=True)
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")

    def elaborate(self, platform):
        m = Module()

        # make a series of "eqs", splitting a and b into partition chunks
        chunks = self.width // self.mwidth
        eqs = Signal(self.mwidth, reset_less=True)
        eql = []
        keys = self.partition_points.keys()
        for i in range(len(keys)-1):
            start, end = keys[i], keys[i+1]
            eql.append(self.a[start:end] == self.b[start:end])
        m.d.comb += eqs.eq(Cat(*l))

        # now, based on the partition points, create the (multi-)boolean result
        m.d.comb += self.out.eq(eqs) # TODO: respect partition points

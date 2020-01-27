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
        self.mwidth = len(self.partition_points)+1
        self.output = Signal(self.mwidth, reset_less=True)
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        # make a series of "eqs", splitting a and b into partition chunks
        eqs = Signal(self.mwidth, reset_less=True)
        eql = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            eql.append(self.a[start:end] == self.b[start:end])
            start = end # for next time round loop
        comb += eqs.eq(Cat(*eql))

        # now, based on the partition points, create the (multi-)boolean result
        # this is a terrible way to do it, it's very laborious.  however it
        # will actually "work".  optimisations come later
        eqsigs = []
        idxs = list(range(self.mwidth))
        idxs.reverse()
        for i in range(self.mwidth):
            eqsig = Signal(name="eqsig%d"%i, reset_less=True)
            eqsigs.append(eqsig)
        for i in idxs:
            if i == 0:
                comb += eqsigs[i].eq(eqs[i])
            else:
                ppt = ~self.partition_points[keys[i-1]]
                comb += eqsigs[i].eq((eqsigs[i-1] & ppt) | ~eqs[i])
        print ("eqsigs", eqsigs, self.output.shape())

        # assign cascade-SIMD-compares to output
        comb += self.output.eq(Cat(*eqsigs))

        return m

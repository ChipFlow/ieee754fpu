# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamically-partitionable "comparison" class, directly equivalent
to Signal.__ge__ except SIMD-partitionable

See:

* http://libre-riscv.org/3d_gpu/architecture/dynamic_simd/ge
* http://bugs.libre-riscv.org/show_bug.cgi?id=132
"""

from nmigen import Signal, Module, Elaboratable, Cat, C, Mux, Repl
from nmigen.cli import main

from ieee754.part_mul_add.partpoints import PartitionPoints

def create_ge(nes, les, start, count):
    """create a greater-than-or-equal from partitioned eqs and greaterthans

        this works by doing:  lt3 |
                             (lt2 & eq3) |
                             (lt1 & eq3 & eq2) |
                             (lt0 & eq3 & eq2 & eq1)
    """
    res = []
    for i in range(count-1):
        ands = [les[start+count-1]] # always one, and it's the end one
        res.append(les[start+i])


class PartitionedGe(Elaboratable):

    def __init__(self, width, partition_points):
        """Create a ``PartitionedGe`` operator
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

        # see equal.py notes

        # prepare the output bits (name them for convenience)
        gtsigs = []
        for i in range(self.mwidth):
            gtsig = Signal(name="gtsig%d"%i, reset_less=True)
            gtsigs.append(gtsig)

        # make series of !eqs and !gts, splitting a and b into partition chunks
        nes = Signal(self.mwidth, reset_less=True)
        les = Signal(self.mwidth, reset_less=True)
        nel = []
        lel = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            nel.append(self.a[start:end] != self.b[start:end]) # see bool below
            lel.append(self.a[start:end] <= self.b[start:end]) # see bool below
            start = end # for next time round loop
        comb += nes.eq(Cat(*nel))
        comb += les.eq(Cat(*nel))

        # now, based on the partition points, create the (multi-)boolean result
        # this is a terrible way to do it, it's very laborious.  however it
        # will actually "work".  optimisations come later

        # we want just the partition points, as a number
        ppoints = Signal(self.mwidth-1)
        comb += ppoints.eq(self.partition_points.as_sig())

        with m.Switch(ppoints):
            for pval in range(1<<(self.mwidth-1)): # for each partition point
                # identify (find-first) transition points, and how
                # long each partition is
                start = 0
                count = 1
                idx = [0] * self.mwidth
                for ipdx in range((self.mwidth-1)):
                    if (pval & (1<<ipdx)):
                        idx[start] = count
                        start = ipdx + 1
                        count = 1
                    else:
                        count += 1
                idx[start] = count # update last point (or create it)

                # now for each partition combination,
                with m.Case(pval):
                    #print (pval, bin(pval), idx)
                    for i in range(self.mwidth):
                        n = "andsig_%d_%d" % (pval, i)
                        if not idx[start]:
                            continue
                        ands = create_ge(nes, les, i, idx[start])
                        andsig = Signal(len(ands), name=n, reset_less=True)
                        ands = ands.bool() # create an AND cascade
                        #print ("ands", pval, i, ands)
                        comb += andsig.eq(ands)
                        comb += gtsigs[i].eq(~andsig) # here's the inversion

        # assign cascade-SIMD-compares to output
        comb += self.output.eq(Cat(*gtsigs))

        return m

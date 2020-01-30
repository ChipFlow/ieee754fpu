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

        # ok first thing to note, before reading this (read the wiki page
        # first), according to boolean algebra, these two are equivalent:
        # (~[~eq0, ~eq1, ~eq2].bool()) is the same as (eq0 AND eq1 AND eq2)
        # where bool() is the *OR* of all bits in the list.
        #
        # given that ~eqN is neN (not equal), we first create a series
        # of != comparisons on the partitions, then chain the relevant
        # ones together depending on partition points, BOOL those together
        # and invert the result.
        #
        # the outer loop is on the partition value.  the preparation phase
        # (idx array) is to work out how and when the eqs (ne's) are to be
        # chained together.  finally an inner loop - one per bit - grabs
        # each chain, on a per-output-bit basis.
        #
        # the result is that for each partition-point permutation you get
        # a different set of output results for each bit.  it's... messy
        # but functional.

        # prepare the output bits (name them for convenience)
        eqsigs = []
        for i in range(self.mwidth):
            eqsig = Signal(name="eqsig%d"%i, reset_less=True)
            eqsigs.append(eqsig)

        # make a series of "not-eqs", splitting a and b into partition chunks
        nes = Signal(self.mwidth, reset_less=True)
        nel = []
        keys = list(self.partition_points.keys()) + [self.width]
        start = 0
        for i in range(len(keys)):
            end = keys[i]
            nel.append(self.a[start:end] != self.b[start:end]) # see bool below
            start = end # for next time round loop
        comb += nes.eq(Cat(*nel))

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
                        ands = nes[i:i+idx[start]]
                        andsig = Signal(len(ands), name=n, reset_less=True)
                        ands = ands.bool() # create an AND cascade
                        #print ("ands", pval, i, ands)
                        comb += andsig.eq(ands)
                        comb += eqsigs[i].eq(~andsig) # here's the inversion

        # assign cascade-SIMD-compares to output
        comb += self.output.eq(Cat(*eqsigs))

        return m

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
        #bitrange = int(math.floor(math.log(self.mwidth-1)/math.log(2)))
        # first loop on bits in output
        olist = []
        for i in range(self.mwidth):
            eqsig = Signal(name="eqsig%d"%i, reset_less=True)
            eqsigs.append(eqsig)
            olist.append([])

        ppoints = Signal(self.mwidth-1)
        comb += ppoints.eq(self.partition_points.as_sig())

        for pval in range(1<<(self.mwidth-1)): # for each partition point
            cpv = C(pval, self.mwidth-1)
            with m.If(ppoints == cpv):
                # identify (find-first) transition points, and how long each
                # partition is
                start = 0
                count = 1
                idx = [0] * self.mwidth
                psigs = []
                for ipdx in range((self.mwidth-1)):
                    pt = ppoints[ipdx]
                    if pval & (1<<ipdx):
                        pt = ~pt
                    psigs.append(pt) # see AND-cascade trick
                    if pval & (1<<ipdx):
                        idx[start] = count
                        start = ipdx + 1
                        count = 1
                    else:
                        count += 1
                idx[start] = count # update last point (or create it)

                print (pval, idx)
                for i in range(self.mwidth):
                    ands = [] # collate a chain of eqs together
                    for j in range(idx[i]):
                        ands.append(~eqs[i+j]) # see AND-cascade trick
                    name = "andsig_%d_%d" % (pval, i)
                    if ands:
                        andsig = Signal(len(ands), name=name, reset_less=True)
                        ands = ~Cat(*ands).bool() # create an AND cascade
                    else:
                        ands = C(0)
                    comb += andsig.eq(ands)
                    comb += eqsigs[i].eq(andsig)

        print ("eqsigs", eqsigs, self.output.shape())

        # assign cascade-SIMD-compares to output
        comb += self.output.eq(Cat(*eqsigs))

        return m

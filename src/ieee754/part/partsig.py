# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

"""
Copyright (C) 2020 Luke Kenneth Casson Leighton <lkcl@lkcl.net>

dynamic-partitionable class similar to Signal, which, when the partition
is fully open will be identical to Signal.  when partitions are closed,
the class turns into a SIMD variant of Signal.  *this is dynamic*.

the basic fundamental idea is: write code once, and if you want a SIMD
version of it, use PartitionedSignal in place of Signal.  job done.
this however requires the code to *not* be designed to use nmigen.If,
nmigen.Case, or other constructs: only Mux and other logic.

http://bugs.libre-riscv.org/show_bug.cgi?id=132
"""

from ieee754.part_mul_add.adder import PartitionedAdder
from ieee754.part_cmp.equal import PartitionedEq
from ieee754.part_mul_add.partpoints import make_partition

from nmigen import (Signal,
                    )

class PartitionedSignal:
    def __init__(self, mask, *args, **kwargs):
        self.sig = Signal(*args, **kwargs)
        width = self.sig.shape()[0] # get signal width
        self.partpoints = make_partition(mask, width) # create partition points
        self.modnames = {}
        for name in ['add', 'eq']:
            self.modnames[name] = 0

    def set_module(self, m):
        self.m = m

    def get_modname(self, category):
        self.modnames[category] += 1
        return "%s%d" % (category, self.modnames[category])

    def eq(self, val):
        return self.sig.eq(val)

    def __xor__(self, other):
        if isinstance(other, PartitionedSignal):
            return self.sig ^ other.sig
        return self.sig ^ other

    def __add__(self, other):
        shape = self.sig.shape()
        pa = PartitionedAdder(shape[0], self.partpoints)
        setattr(self.m.submodules, self.get_modname('add'), pa)
        comb = self.m.d.comb
        comb += pa.a.eq(self.sig)
        if isinstance(other, PartitionedSignal):
            comb += pa.b.eq(other.sig)
        else:
            comb += pa.b.eq(other)
        return pa.output

    def __eq__(self, other):
        print ("eq", self, other)
        shape = self.sig.shape()
        pa = PartitionedEq(shape[0], self.partpoints)
        setattr(self.m.submodules, self.get_modname('eq'), pa)
        comb = self.m.d.comb
        comb += pa.a.eq(self.sig)
        if isinstance(other, PartitionedSignal):
            comb += pa.b.eq(other.sig)
        else:
            comb += pa.b.eq(other)
        return pa.output

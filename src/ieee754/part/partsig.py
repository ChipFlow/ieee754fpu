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
#from ieee754.part_cmp.equal_ortree import PartitionedEq
from ieee754.part_cmp.eq_gt_ge import PartitionedEqGtGe
from ieee754.part_mul_add.partpoints import make_partition
from operator import or_, xor, and_, not_

from nmigen import (Signal,
                    )
def applyop(op1, op2, op):
    if isinstance(op1, PartitionedSignal):
        op1 = op1.sig
    if isinstance(op2, PartitionedSignal):
        op2 = op2.sig
    return op(op1, op2)


class PartitionedSignal:
    def __init__(self, mask, *args, **kwargs):
        self.sig = Signal(*args, **kwargs)
        width = self.sig.shape()[0] # get signal width
        self.partpoints = make_partition(mask, width) # create partition points
        self.modnames = {}
        for name in ['add', 'eq', 'gt', 'ge']:
            self.modnames[name] = 0

    def set_module(self, m):
        self.m = m

    def get_modname(self, category):
        self.modnames[category] += 1
        return "%s%d" % (category, self.modnames[category])

    def eq(self, val):
        return self.sig.eq(val)

    def __and__(self, other):
        return applyop(self, other, and_)

    def __rand__(self, other):
        return applyop(other, self, and_)

    def __or__(self, other):
        return applyop(self, other, or_)

    def __ror__(self, other):
        return applyop(other, self, or_)

    def __xor__(self, other):
        return applyop(self, other, xor)

    def __rxor__(self, other):
        return applyop(other, self, xor)

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

    def _compare(self, width, op1, op2, opname, optype):
        #print (opname, op1, op2)
        pa = PartitionedEqGtGe(width, self.partpoints)
        setattr(self.m.submodules, self.get_modname(opname), pa)
        comb = self.m.d.comb
        comb += pa.opcode.eq(optype) # set opcode
        if isinstance(op1, PartitionedSignal):
            comb += pa.a.eq(op1.sig)
        else:
            comb += pa.a.eq(op1)
        if isinstance(op2, PartitionedSignal):
            comb += pa.b.eq(op2.sig)
        else:
            comb += pa.b.eq(op2)
        return pa.output

    def __eq__(self, other):
        width = self.sig.shape()[0]
        return self._compare(width, self, other, "eq", PartitionedEqGtGe.EQ)

    def __ne__(self, other):
        return ~self.__eq__(other)

    def __gt__(self, other):
        width = self.sig.shape()[0]
        return self._compare(width, self, other, "gt", PartitionedEqGtGe.GT)

    def __ge__(self, other):
        width = self.sig.shape()[0]
        return self._compare(width, self, other, "ge", PartitionedEqGtGe.GE)

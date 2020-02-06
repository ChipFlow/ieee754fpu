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

    # unary  ops that require partitioning

    def __invert__(self):
        return Operator("~", [self])
    def __neg__(self):
        return Operator("-", [self])

    # binary ops that don't require partitioning

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

    # binary ops that need partitioning

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

    def __radd__(self, other):
        return Operator("+", [other, self])
    def __sub__(self, other):
        return Operator("-", [self, other])
    def __rsub__(self, other):
        return Operator("-", [other, self])

    def __mul__(self, other):
        return Operator("*", [self, other])
    def __rmul__(self, other):
        return Operator("*", [other, self])

    def __check_divisor(self):
        width, signed = self.shape()
        if signed:
            # Python's division semantics and Verilog's division semantics
            # differ for negative divisors (Python uses div/mod, Verilog
            # uses quo/rem); for now, avoid the issue
            # completely by prohibiting such division operations.
            raise NotImplementedError(
                    "Division by a signed value is not supported")
    def __mod__(self, other):
        other = Value.cast(other)
        other.__check_divisor()
        return Operator("%", [self, other])
    def __rmod__(self, other):
        self.__check_divisor()
        return Operator("%", [other, self])
    def __floordiv__(self, other):
        other = Value.cast(other)
        other.__check_divisor()
        return Operator("//", [self, other])
    def __rfloordiv__(self, other):
        self.__check_divisor()
        return Operator("//", [other, self])

    def __lshift__(self, other):
        return Operator("<<", [self, other])
    def __rlshift__(self, other):
        return Operator("<<", [other, self])
    def __rshift__(self, other):
        return Operator(">>", [self, other])

    # binary comparison ops that need partitioning

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
        width = self.sig.shape()[0]
        invert = ~self.sig # invert the input before compare EQ. TODO: NE op
        return self._compare(width, invert, other, "eq", PartitionedEqGtGe.EQ)

    def __gt__(self, other):
        width = self.sig.shape()[0]
        return self._compare(width, self, other, "gt", PartitionedEqGtGe.GT)

    def __lt__(self, other):
        width = self.sig.shape()[0]
        return self._compare(width, other, self, "gt", PartitionedEqGtGe.GT)

    def __ge__(self, other):
        width = self.sig.shape()[0]
        return self._compare(width, self, other, "ge", PartitionedEqGtGe.GE)

    def __le__(self, other):
        width = self.sig.shape()[0]
        return self._compare(width, other, self, "ge", PartitionedEqGtGe.GE)

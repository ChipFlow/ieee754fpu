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

* http://bugs.libre-riscv.org/show_bug.cgi?id=132
"""

from ieee754.part_mul_add.adder import PartitionedAdder
from ieee754.part_cmp.eq_gt_ge import PartitionedEqGtGe
from ieee754.part_bits.xor import PartitionedXOR
from ieee754.part_shift.part_shift_dynamic import PartitionedDynamicShift
from ieee754.part_shift.part_shift_scalar import PartitionedScalarShift
from ieee754.part_mul_add.partpoints import make_partition, PartitionPoints
from ieee754.part_mux.part_mux import PMux
from operator import or_, xor, and_, not_

from nmigen import (Signal, Const)
from nmigen.hdl.ast import UserValue


def getsig(op1):
    if isinstance(op1, PartitionedSignal):
        op1 = op1.sig
    return op1


def applyop(op1, op2, op):
    if isinstance(op1, PartitionedSignal):
        result = PartitionedSignal.like(op1)
    else:
        result = PartitionedSignal.like(op2)
    result.m.d.comb += result.sig.eq(op(getsig(op1), getsig(op2)))
    return result


class PartitionedSignal(UserValue):
    def __init__(self, mask, *args, src_loc_at=0, **kwargs):
        super().__init__(src_loc_at=src_loc_at)
        self.sig = Signal(*args, **kwargs)
        width = len(self.sig)  # get signal width
        # create partition points
        if isinstance(mask, PartitionPoints):
            self.partpoints = mask
        else:
            self.partpoints = make_partition(mask, width)
        self.modnames = {}
        # for sub-modules to be created on-demand. Mux is done slightly
        # differently
        for name in ['add', 'eq', 'gt', 'ge', 'ls', 'xor']:
            self.modnames[name] = 0

    def lower(self):
        return self.sig

    def set_module(self, m):
        self.m = m

    def get_modname(self, category):
        self.modnames[category] += 1
        return "%s_%d" % (category, self.modnames[category])

    def eq(self, val):
        return self.sig.eq(getsig(val))

    @staticmethod
    def like(other, *args, **kwargs):
        """Builds a new PartitionedSignal with the same PartitionPoints and
        Signal properties as the other"""
        result = PartitionedSignal(other.partpoints)
        result.sig = Signal.like(other.sig, *args, **kwargs)
        result.m = other.m
        return result

    # nmigen-redirected constructs (Mux, Cat, Switch, Assign)

    def __Mux__(self, val1, val2):
        assert len(val1) == len(val2), \
            "PartitionedSignal width sources must be the same " \
            "val1 == %d, val2 == %d" % (len(val1), len(val2))
        return PMux(self.m, self.partpoints, self, val1, val2)

    # unary ops that do not require partitioning

    def __invert__(self):
        result = PartitionedSignal.like(self)
        self.m.d.comb += result.sig.eq(~self.sig)
        return result

    # unary ops that require partitioning

    def __neg__(self):
        z = Const(0, len(self.sig))
        result, _ = self.sub_op(z, self)
        return result

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

    # TODO: detect if the 2nd operand is a Const, a Signal or a
    # PartitionedSignal.  if it's a Const or a Signal, a global shift
    # can occur.  if it's a PartitionedSignal, that's much more interesting.
    def ls_op(self, op1, op2, carry, shr_flag=0):
        op1 = getsig(op1)
        if isinstance(op2, Const) or isinstance(op2, Signal):
            scalar = True
            pa = PartitionedScalarShift(len(op1), self.partpoints)
        else:
            scalar = False
            op2 = getsig(op2)
            pa = PartitionedDynamicShift(len(op1), self.partpoints)
        setattr(self.m.submodules, self.get_modname('ls'), pa)
        comb = self.m.d.comb
        if scalar:
            comb += pa.data.eq(op1)
            comb += pa.shifter.eq(op2)
            comb += pa.shift_right.eq(shr_flag)
        else:
            comb += pa.a.eq(op1)
            comb += pa.b.eq(op2)
            comb += pa.shift_right.eq(shr_flag)
        # XXX TODO: carry-in, carry-out
        #comb += pa.carry_in.eq(carry)
        return (pa.output, 0)

    def __lshift__(self, other):
        z = Const(0, len(self.partpoints)+1)
        result, _ = self.ls_op(self, other, carry=z) # TODO, carry
        return result

    def __rlshift__(self, other):
        raise NotImplementedError
        return Operator("<<", [other, self])

    def __rshift__(self, other):
        z = Const(0, len(self.partpoints)+1)
        result, _ = self.ls_op(self, other, carry=z, shr_flag=1) # TODO, carry
        return result

    def __rrshift__(self, other):
        raise NotImplementedError
        return Operator(">>", [other, self])

    def add_op(self, op1, op2, carry):
        op1 = getsig(op1)
        op2 = getsig(op2)
        pa = PartitionedAdder(len(op1), self.partpoints)
        setattr(self.m.submodules, self.get_modname('add'), pa)
        comb = self.m.d.comb
        comb += pa.a.eq(op1)
        comb += pa.b.eq(op2)
        comb += pa.carry_in.eq(carry)
        result = PartitionedSignal.like(self)
        comb += result.sig.eq(pa.output)
        return result, pa.carry_out

    def sub_op(self, op1, op2, carry=~0):
        op1 = getsig(op1)
        op2 = getsig(op2)
        pa = PartitionedAdder(len(op1), self.partpoints)
        setattr(self.m.submodules, self.get_modname('add'), pa)
        comb = self.m.d.comb
        comb += pa.a.eq(op1)
        comb += pa.b.eq(~op2)
        comb += pa.carry_in.eq(carry)
        result = PartitionedSignal.like(self)
        comb += result.sig.eq(pa.output)
        return result, pa.carry_out

    def __add__(self, other):
        result, _ = self.add_op(self, other, carry=0)
        return result

    def __radd__(self, other):
        result, _ = self.add_op(other, self)
        return result

    def __sub__(self, other):
        result, _ = self.sub_op(self, other)
        return result

    def __rsub__(self, other):
        result, _ = self.sub_op(other, self)
        return result

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
        raise NotImplementedError
        other = Value.cast(other)
        other.__check_divisor()
        return Operator("%", [self, other])

    def __rmod__(self, other):
        raise NotImplementedError
        self.__check_divisor()
        return Operator("%", [other, self])

    def __floordiv__(self, other):
        raise NotImplementedError
        other = Value.cast(other)
        other.__check_divisor()
        return Operator("//", [self, other])

    def __rfloordiv__(self, other):
        raise NotImplementedError
        self.__check_divisor()
        return Operator("//", [other, self])

    # binary comparison ops that need partitioning

    def _compare(self, width, op1, op2, opname, optype):
        # print (opname, op1, op2)
        pa = PartitionedEqGtGe(width, self.partpoints)
        setattr(self.m.submodules, self.get_modname(opname), pa)
        comb = self.m.d.comb
        comb += pa.opcode.eq(optype)  # set opcode
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
        width = len(self.sig)
        return self._compare(width, self, other, "eq", PartitionedEqGtGe.EQ)

    def __ne__(self, other):
        width = len(self.sig)
        eq = self._compare(width, self, other, "eq", PartitionedEqGtGe.EQ)
        ne = Signal(eq.width)
        self.m.d.comb += ne.eq(~eq)
        return ne

    def __gt__(self, other):
        width = len(self.sig)
        return self._compare(width, self, other, "gt", PartitionedEqGtGe.GT)

    def __lt__(self, other):
        width = len(self.sig)
        # swap operands, use gt to do lt
        return self._compare(width, other, self, "gt", PartitionedEqGtGe.GT)

    def __ge__(self, other):
        width = len(self.sig)
        return self._compare(width, self, other, "ge", PartitionedEqGtGe.GE)

    def __le__(self, other):
        width = len(self.sig)
        # swap operands, use ge to do le
        return self._compare(width, other, self, "ge", PartitionedEqGtGe.GE)

    # useful operators

    def bool(self):
        """Conversion to boolean.

        Returns
        -------
        Value, out
            ``1`` if any bits are set, ``0`` otherwise.
        """
        return self.any() # have to see how this goes
        #return Operator("b", [self])

    def any(self):
        """Check if any bits are ``1``.

        Returns
        -------
        Value, out
            ``1`` if any bits are set, ``0`` otherwise.
        """
        return self != Const(0) # leverage the __ne__ operator here
        return Operator("r|", [self])

    def all(self):
        """Check if all bits are ``1``.

        Returns
        -------
        Value, out
            ``1`` if all bits are set, ``0`` otherwise.
        """
        return self == Const(-1) # leverage the __eq__ operator here

    def xor(self):
        """Compute pairwise exclusive-or of every bit.

        Returns
        -------
        Value, out
            ``1`` if an odd number of bits are set, ``0`` if an
                  even number of bits are set.
        """
        width = len(self.sig)
        pa = PartitionedXOR(width, self.partpoints)
        setattr(self.m.submodules, self.get_modname("xor"), pa)
        self.m.d.comb += pa.a.eq(self.sig)
        return pa.output

    def implies(premise, conclusion):
        """Implication.

        Returns
        -------
        Value, out
            ``0`` if ``premise`` is true and ``conclusion`` is not,
            ``1`` otherwise.
        """
        # amazingly, this should actually work.
        return ~premise | conclusion

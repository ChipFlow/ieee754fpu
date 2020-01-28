# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
"""Integer Multiplication."""

from nmigen import Signal, Module, Value, Elaboratable, Cat, C, Mux, Repl
from nmigen.hdl.ast import Assign
from abc import ABCMeta, abstractmethod
from nmigen.cli import main
from functools import reduce
from operator import or_
from ieee754.pipeline import PipelineSpec
from nmutil.pipemodbase import PipeModBase

from ieee754.part_mul_add.partpoints import PartitionPoints


class FullAdder(Elaboratable):
    """Full Adder.

    :attribute in0: the first input
    :attribute in1: the second input
    :attribute in2: the third input
    :attribute sum: the sum output
    :attribute carry: the carry output

    Rather than do individual full adders (and have an array of them,
    which would be very slow to simulate), this module can specify the
    bit width of the inputs and outputs: in effect it performs multiple
    Full 3-2 Add operations "in parallel".
    """

    def __init__(self, width):
        """Create a ``FullAdder``.

        :param width: the bit width of the input and output
        """
        self.in0 = Signal(width, reset_less=True)
        self.in1 = Signal(width, reset_less=True)
        self.in2 = Signal(width, reset_less=True)
        self.sum = Signal(width, reset_less=True)
        self.carry = Signal(width, reset_less=True)

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()
        m.d.comb += self.sum.eq(self.in0 ^ self.in1 ^ self.in2)
        m.d.comb += self.carry.eq((self.in0 & self.in1)
                                  | (self.in1 & self.in2)
                                  | (self.in2 & self.in0))
        return m


class MaskedFullAdder(Elaboratable):
    """Masked Full Adder.

    :attribute mask: the carry partition mask
    :attribute in0: the first input
    :attribute in1: the second input
    :attribute in2: the third input
    :attribute sum: the sum output
    :attribute mcarry: the masked carry output

    FullAdders are always used with a "mask" on the output.  To keep
    the graphviz "clean", this class performs the masking here rather
    than inside a large for-loop.

    See the following discussion as to why this is no longer derived
    from FullAdder.  Each carry is shifted here *before* being ANDed
    with the mask, so that an AOI cell may be used (which is more
    gate-efficient)
    https://en.wikipedia.org/wiki/AND-OR-Invert
    https://groups.google.com/d/msg/comp.arch/fcq-GLQqvas/vTxmcA0QAgAJ
    """

    def __init__(self, width):
        """Create a ``MaskedFullAdder``.

        :param width: the bit width of the input and output
        """
        self.width = width
        self.mask = Signal(width, reset_less=True)
        self.mcarry = Signal(width, reset_less=True)
        self.in0 = Signal(width, reset_less=True)
        self.in1 = Signal(width, reset_less=True)
        self.in2 = Signal(width, reset_less=True)
        self.sum = Signal(width, reset_less=True)

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()
        s1 = Signal(self.width, reset_less=True)
        s2 = Signal(self.width, reset_less=True)
        s3 = Signal(self.width, reset_less=True)
        c1 = Signal(self.width, reset_less=True)
        c2 = Signal(self.width, reset_less=True)
        c3 = Signal(self.width, reset_less=True)
        m.d.comb += self.sum.eq(self.in0 ^ self.in1 ^ self.in2)
        m.d.comb += s1.eq(Cat(0, self.in0))
        m.d.comb += s2.eq(Cat(0, self.in1))
        m.d.comb += s3.eq(Cat(0, self.in2))
        m.d.comb += c1.eq(s1 & s2 & self.mask)
        m.d.comb += c2.eq(s2 & s3 & self.mask)
        m.d.comb += c3.eq(s3 & s1 & self.mask)
        m.d.comb += self.mcarry.eq(c1 | c2 | c3)
        return m


class PartitionedAdder(Elaboratable):
    """Partitioned Adder.

    Performs the final add.  The partition points are included in the
    actual add (in one of the operands only), which causes a carry over
    to the next bit.  Then the final output *removes* the extra bits from
    the result.

    partition: .... P... P... P... P... (32 bits)
    a        : .... .... .... .... .... (32 bits)
    b        : .... .... .... .... .... (32 bits)
    exp-a    : ....P....P....P....P.... (32+4 bits, P=1 if no partition)
    exp-b    : ....0....0....0....0.... (32 bits plus 4 zeros)
    exp-o    : ....xN...xN...xN...xN... (32+4 bits - x to be discarded)
    o        : .... N... N... N... N... (32 bits - x ignored, N is carry-over)

    :attribute width: the bit width of the input and output. Read-only.
    :attribute a: the first input to the adder
    :attribute b: the second input to the adder
    :attribute output: the sum output
    :attribute partition_points: the input partition points. Modification not
        supported, except for by ``Signal.eq``.
    """

    def __init__(self, width, partition_points, partition_step=1):
        """Create a ``PartitionedAdder``.

        :param width: the bit width of the input and output
        :param partition_points: the input partition points
        :param partition_step: a multiplier (typically double) step
                               which in-place "expands" the partition points
        """
        self.width = width
        self.pmul = partition_step
        self.a = Signal(width, reset_less=True)
        self.b = Signal(width, reset_less=True)
        self.output = Signal(width, reset_less=True)
        self.partition_points = PartitionPoints(partition_points)
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")
        expanded_width = 0
        for i in range(self.width):
            if i in self.partition_points:
                expanded_width += 1
            expanded_width += 1
        self._expanded_width = expanded_width

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()
        expanded_a = Signal(self._expanded_width, reset_less=True)
        expanded_b = Signal(self._expanded_width, reset_less=True)
        expanded_o = Signal(self._expanded_width, reset_less=True)

        expanded_index = 0
        # store bits in a list, use Cat later.  graphviz is much cleaner
        al, bl, ol, ea, eb, eo = [],[],[],[],[],[]

        # partition points are "breaks" (extra zeros or 1s) in what would
        # otherwise be a massive long add.  when the "break" points are 0,
        # whatever is in it (in the output) is discarded.  however when
        # there is a "1", it causes a roll-over carry to the *next* bit.
        # we still ignore the "break" bit in the [intermediate] output,
        # however by that time we've got the effect that we wanted: the
        # carry has been carried *over* the break point.

        for i in range(self.width):
            pi = i/self.pmul # double the range of the partition point test
            if pi.is_integer() and pi in self.partition_points:
                # add extra bit set to 0 + 0 for enabled partition points
                # and 1 + 0 for disabled partition points
                ea.append(expanded_a[expanded_index])
                al.append(~self.partition_points[pi]) # add extra bit in a
                eb.append(expanded_b[expanded_index])
                bl.append(C(0)) # yes, add a zero
                expanded_index += 1 # skip the extra point.  NOT in the output
            ea.append(expanded_a[expanded_index])
            eb.append(expanded_b[expanded_index])
            eo.append(expanded_o[expanded_index])
            al.append(self.a[i])
            bl.append(self.b[i])
            ol.append(self.output[i])
            expanded_index += 1

        # combine above using Cat
        m.d.comb += Cat(*ea).eq(Cat(*al))
        m.d.comb += Cat(*eb).eq(Cat(*bl))
        m.d.comb += Cat(*ol).eq(Cat(*eo))

        # use only one addition to take advantage of look-ahead carry and
        # special hardware on FPGAs
        m.d.comb += expanded_o.eq(expanded_a + expanded_b)
        return m


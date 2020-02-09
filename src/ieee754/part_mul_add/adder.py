# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
"""Partitioned Integer Addition.

See:
* https://libre-riscv.org/3d_gpu/architecture/dynamic_simd/add/
"""

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
        comb = m.d.comb
        comb += self.sum.eq(self.in0 ^ self.in1 ^ self.in2)
        comb += self.carry.eq((self.in0 & self.in1)
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
        comb = m.d.comb
        s1 = Signal(self.width, reset_less=True)
        s2 = Signal(self.width, reset_less=True)
        s3 = Signal(self.width, reset_less=True)
        c1 = Signal(self.width, reset_less=True)
        c2 = Signal(self.width, reset_less=True)
        c3 = Signal(self.width, reset_less=True)
        comb += self.sum.eq(self.in0 ^ self.in1 ^ self.in2)
        comb += s1.eq(Cat(0, self.in0))
        comb += s2.eq(Cat(0, self.in1))
        comb += s3.eq(Cat(0, self.in2))
        comb += c1.eq(s1 & s2 & self.mask)
        comb += c2.eq(s2 & s3 & self.mask)
        comb += c3.eq(s3 & s1 & self.mask)
        comb += self.mcarry.eq(c1 | c2 | c3)
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

    partition:      p    p    p    p      (4 bits)
    carry-in :           c    c    c    c (4 bits)
    C = c & P:           C    C    C    c (4 bits)
    I = P=>c :           I    I    I    I (4 bits)
    a        :  AAAA AAAA AAAA AAAA AAAA  (32 bits)
    b        :  BBBB BBBB BBBB BBBB BBBB  (32 bits)
    exp-a    : 0AAAApAAAACAAAACAAAACAAAAc (32+4 bits, P=1 if no partition)
    exp-b    : 0BBBB0BBBBIBBBBIBBBBIBBBBI (32 bits plus 4 zeros)
    exp-o    : o....oN...oN...oN...oN...x (32+4 bits - x to be discarded)
    o        :  .... N... N... N... N... (32 bits - x ignored, N is carry-over)
    carry-out:      o    o    o    o      (4 bits)

    :attribute width: the bit width of the input and output. Read-only.
    :attribute a: the first input to the adder
    :attribute b: the second input to the adder
    :attribute output: the sum output
    :attribute part_pts: the input partition points. Modification not
        supported, except for by ``Signal.eq``.
    """

    def __init__(self, width, part_pts, partition_step=1):
        """Create a ``PartitionedAdder``.

        :param width: the bit width of the input and output
        :param part_pts: the input partition points
        :param partition_step: a multiplier (typically double) step
                               which in-place "expands" the partition points
        """
        self.width = width
        self.pmul = partition_step
        self.part_pts = PartitionPoints(part_pts)
        self.a = Signal(width, reset_less=True)
        self.b = Signal(width, reset_less=True)
        self.carry_in = Signal(self.part_pts.get_max_partition_count(width))
        self.carry_out = Signal(self.part_pts.get_max_partition_count(width))
        self.output = Signal(width, reset_less=True)
        if not self.part_pts.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")
        expanded_width = 2
        for i in range(self.width):
            if i in self.part_pts:
                expanded_width += 1
            expanded_width += 1
        self._expanded_width = expanded_width

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()
        comb = m.d.comb
        expanded_a = Signal(self._expanded_width, reset_less=True)
        expanded_b = Signal(self._expanded_width, reset_less=True)
        expanded_o = Signal(self._expanded_width, reset_less=True)

        expanded_index = 0
        # store bits in a list, use Cat later.  graphviz is much cleaner
        al, bl, ol, cl, ea, eb, eo, co = [],[],[],[],[],[],[],[]

        # partition points are "breaks" (extra zeros or 1s) in what would
        # otherwise be a massive long add.  when the "break" points are 0,
        # whatever is in it (in the output) is discarded.  however when
        # there is a "1", it causes a roll-over carry to the *next* bit.
        # we still ignore the "break" bit in the [intermediate] output,
        # however by that time we've got the effect that we wanted: the
        # carry has been carried *over* the break point.

        carry_bit = 0
        al.append(self.carry_in[carry_bit])
        bl.append(self.carry_in[carry_bit])
        ea.append(expanded_a[expanded_index])
        eb.append(expanded_b[expanded_index])
        carry_bit += 1
        expanded_index += 1

        for i in range(self.width):
            pi = i/self.pmul # double the range of the partition point test
            if pi.is_integer() and pi in self.part_pts:
                # add extra bit set to 0 + 0 for enabled partition points
                a_bit = Signal(name="a_bit_%d" % i, reset_less=True)
                carry_in = self.carry_in[carry_bit] # convenience
                m.d.comb += a_bit.eq(self.part_pts[pi].implies(carry_in))
                # and 1 + 0 for disabled partition points
                ea.append(expanded_a[expanded_index])
                al.append(a_bit) # add extra bit in a
                eb.append(expanded_b[expanded_index])
                bl.append(carry_in & self.part_pts[pi]) # yes, add a zero
                co.append(expanded_o[expanded_index])
                cl.append(self.carry_out[carry_bit-1])
                expanded_index += 1 # skip the extra point.  NOT in the output
                carry_bit += 1
            ea.append(expanded_a[expanded_index])
            eb.append(expanded_b[expanded_index])
            eo.append(expanded_o[expanded_index])
            al.append(self.a[i])
            bl.append(self.b[i])
            ol.append(self.output[i])
            expanded_index += 1
        al.append(0)
        bl.append(0)
        co.append(expanded_o[expanded_index])
        cl.append(self.carry_out[carry_bit-1])

        # combine above using Cat
        comb += Cat(*ea).eq(Cat(*al))
        comb += Cat(*eb).eq(Cat(*bl))
        comb += Cat(*ol).eq(Cat(*eo))
        comb += Cat(*cl).eq(Cat(*co))

        # use only one addition to take advantage of look-ahead carry and
        # special hardware on FPGAs
        comb += expanded_o.eq(expanded_a + expanded_b)

        return m



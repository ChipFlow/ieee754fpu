# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
"""Integer Multiplication."""

from nmigen import Signal, Module, Value, Elaboratable, Cat, C, Mux, Repl
from nmigen.hdl.ast import Assign
from abc import ABCMeta, abstractmethod
from nmigen.cli import main
from functools import reduce
from operator import or_


class PartitionPoints(dict):
    """Partition points and corresponding ``Value``s.

    The points at where an ALU is partitioned along with ``Value``s that
    specify if the corresponding partition points are enabled.

    For example: ``{1: True, 5: True, 10: True}`` with
    ``width == 16`` specifies that the ALU is split into 4 sections:
    * bits 0 <= ``i`` < 1
    * bits 1 <= ``i`` < 5
    * bits 5 <= ``i`` < 10
    * bits 10 <= ``i`` < 16

    If the partition_points were instead ``{1: True, 5: a, 10: True}``
    where ``a`` is a 1-bit ``Signal``:
    * If ``a`` is asserted:
        * bits 0 <= ``i`` < 1
        * bits 1 <= ``i`` < 5
        * bits 5 <= ``i`` < 10
        * bits 10 <= ``i`` < 16
    * Otherwise
        * bits 0 <= ``i`` < 1
        * bits 1 <= ``i`` < 10
        * bits 10 <= ``i`` < 16
    """

    def __init__(self, partition_points=None):
        """Create a new ``PartitionPoints``.

        :param partition_points: the input partition points to values mapping.
        """
        super().__init__()
        if partition_points is not None:
            for point, enabled in partition_points.items():
                if not isinstance(point, int):
                    raise TypeError("point must be a non-negative integer")
                if point < 0:
                    raise ValueError("point must be a non-negative integer")
                self[point] = Value.wrap(enabled)

    def like(self, name=None, src_loc_at=0):
        """Create a new ``PartitionPoints`` with ``Signal``s for all values.

        :param name: the base name for the new ``Signal``s.
        """
        if name is None:
            name = Signal(src_loc_at=1+src_loc_at).name  # get variable name
        retval = PartitionPoints()
        for point, enabled in self.items():
            retval[point] = Signal(enabled.shape(), name=f"{name}_{point}")
        return retval

    def eq(self, rhs):
        """Assign ``PartitionPoints`` using ``Signal.eq``."""
        if set(self.keys()) != set(rhs.keys()):
            raise ValueError("incompatible point set")
        for point, enabled in self.items():
            yield enabled.eq(rhs[point])

    def as_mask(self, width):
        """Create a bit-mask from `self`.

        Each bit in the returned mask is clear only if the partition point at
        the same bit-index is enabled.

        :param width: the bit width of the resulting mask
        """
        bits = []
        for i in range(width):
            if i in self:
                bits.append(~self[i])
            else:
                bits.append(True)
        return Cat(*bits)

    def get_max_partition_count(self, width):
        """Get the maximum number of partitions.

        Gets the number of partitions when all partition points are enabled.
        """
        retval = 1
        for point in self.keys():
            if point < width:
                retval += 1
        return retval

    def fits_in_width(self, width):
        """Check if all partition points are smaller than `width`."""
        for point in self.keys():
            if point >= width:
                return False
        return True


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
        self.in0 = Signal(width)
        self.in1 = Signal(width)
        self.in2 = Signal(width)
        self.sum = Signal(width)
        self.carry = Signal(width)

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

    def __init__(self, width, partition_points):
        """Create a ``PartitionedAdder``.

        :param width: the bit width of the input and output
        :param partition_points: the input partition points
        """
        self.width = width
        self.a = Signal(width)
        self.b = Signal(width)
        self.output = Signal(width)
        self.partition_points = PartitionPoints(partition_points)
        if not self.partition_points.fits_in_width(width):
            raise ValueError("partition_points doesn't fit in width")
        expanded_width = 0
        for i in range(self.width):
            if i in self.partition_points:
                expanded_width += 1
            expanded_width += 1
        self._expanded_width = expanded_width
        # XXX these have to remain here due to some horrible nmigen
        # simulation bugs involving sync.  it is *not* necessary to
        # have them here, they should (under normal circumstances)
        # be moved into elaborate, as they are entirely local
        self._expanded_a = Signal(expanded_width) # includes extra part-points
        self._expanded_b = Signal(expanded_width) # likewise.
        self._expanded_o = Signal(expanded_width) # likewise.

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()
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
            if i in self.partition_points:
                # add extra bit set to 0 + 0 for enabled partition points
                # and 1 + 0 for disabled partition points
                ea.append(self._expanded_a[expanded_index])
                al.append(~self.partition_points[i]) # add extra bit in a
                eb.append(self._expanded_b[expanded_index])
                bl.append(C(0)) # yes, add a zero
                expanded_index += 1 # skip the extra point.  NOT in the output
            ea.append(self._expanded_a[expanded_index])
            eb.append(self._expanded_b[expanded_index])
            eo.append(self._expanded_o[expanded_index])
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
        m.d.comb += self._expanded_o.eq(
            self._expanded_a + self._expanded_b)
        return m


FULL_ADDER_INPUT_COUNT = 3


class AddReduceSingle(Elaboratable):
    """Add list of numbers together.

    :attribute inputs: input ``Signal``s to be summed. Modification not
        supported, except for by ``Signal.eq``.
    :attribute register_levels: List of nesting levels that should have
        pipeline registers.
    :attribute output: output sum.
    :attribute partition_points: the input partition points. Modification not
        supported, except for by ``Signal.eq``.
    """

    def __init__(self, inputs, output_width, register_levels, partition_points):
        """Create an ``AddReduce``.

        :param inputs: input ``Signal``s to be summed.
        :param output_width: bit-width of ``output``.
        :param register_levels: List of nesting levels that should have
            pipeline registers.
        :param partition_points: the input partition points.
        """
        self.inputs = list(inputs)
        self._resized_inputs = [
            Signal(output_width, name=f"resized_inputs[{i}]")
            for i in range(len(self.inputs))]
        self.register_levels = list(register_levels)
        self.output = Signal(output_width)
        self.partition_points = PartitionPoints(partition_points)
        if not self.partition_points.fits_in_width(output_width):
            raise ValueError("partition_points doesn't fit in output_width")
        self._reg_partition_points = self.partition_points.like()

        max_level = AddReduce.get_max_level(len(self.inputs))
        for level in self.register_levels:
            if level > max_level:
                raise ValueError(
                    "not enough adder levels for specified register levels")

    @staticmethod
    def get_max_level(input_count):
        """Get the maximum level.

        All ``register_levels`` must be less than or equal to the maximum
        level.
        """
        retval = 0
        while True:
            groups = AddReduce.full_adder_groups(input_count)
            if len(groups) == 0:
                return retval
            input_count %= FULL_ADDER_INPUT_COUNT
            input_count += 2 * len(groups)
            retval += 1
    @staticmethod
    def full_adder_groups(input_count):
        """Get ``inputs`` indices for which a full adder should be built."""
        return range(0,
                     input_count - FULL_ADDER_INPUT_COUNT + 1,
                     FULL_ADDER_INPUT_COUNT)

    def _elaborate(self, platform):
        """Elaborate this module."""
        m = Module()

        # resize inputs to correct bit-width and optionally add in
        # pipeline registers
        resized_input_assignments = [self._resized_inputs[i].eq(self.inputs[i])
                                     for i in range(len(self.inputs))]
        if 0 in self.register_levels:
            m.d.sync += resized_input_assignments
            m.d.sync += self._reg_partition_points.eq(self.partition_points)
        else:
            m.d.comb += resized_input_assignments
            m.d.comb += self._reg_partition_points.eq(self.partition_points)

        groups = AddReduceSingle.full_adder_groups(len(self.inputs))
        # if there are no full adders to create, then we handle the base cases
        # and return, otherwise we go on to the recursive case
        if len(groups) == 0:
            if len(self.inputs) == 0:
                # use 0 as the default output value
                m.d.comb += self.output.eq(0)
            elif len(self.inputs) == 1:
                # handle single input
                m.d.comb += self.output.eq(self._resized_inputs[0])
            else:
                # base case for adding 2 or more inputs, which get recursively
                # reduced to 2 inputs
                assert len(self.inputs) == 2
                adder = PartitionedAdder(len(self.output),
                                         self._reg_partition_points)
                m.submodules.final_adder = adder
                m.d.comb += adder.a.eq(self._resized_inputs[0])
                m.d.comb += adder.b.eq(self._resized_inputs[1])
                m.d.comb += self.output.eq(adder.output)
            return None, m

        # go on to prepare recursive case
        intermediate_terms = []

        def add_intermediate_term(value):
            intermediate_term = Signal(
                len(self.output),
                name=f"intermediate_terms[{len(intermediate_terms)}]")
            intermediate_terms.append(intermediate_term)
            m.d.comb += intermediate_term.eq(value)

        # store mask in intermediary (simplifies graph)
        part_mask = Signal(len(self.output), reset_less=True)
        mask = self._reg_partition_points.as_mask(len(self.output))
        m.d.comb += part_mask.eq(mask)

        # create full adders for this recursive level.
        # this shrinks N terms to 2 * (N // 3) plus the remainder
        for i in groups:
            adder_i = MaskedFullAdder(len(self.output))
            setattr(m.submodules, f"adder_{i}", adder_i)
            m.d.comb += adder_i.in0.eq(self._resized_inputs[i])
            m.d.comb += adder_i.in1.eq(self._resized_inputs[i + 1])
            m.d.comb += adder_i.in2.eq(self._resized_inputs[i + 2])
            m.d.comb += adder_i.mask.eq(part_mask)
            # add both the sum and the masked-carry to the next level.
            # 3 inputs have now been reduced to 2...
            add_intermediate_term(adder_i.sum)
            add_intermediate_term(adder_i.mcarry)
        # handle the remaining inputs.
        if len(self.inputs) % FULL_ADDER_INPUT_COUNT == 1:
            add_intermediate_term(self._resized_inputs[-1])
        elif len(self.inputs) % FULL_ADDER_INPUT_COUNT == 2:
            # Just pass the terms to the next layer, since we wouldn't gain
            # anything by using a half adder since there would still be 2 terms
            # and just passing the terms to the next layer saves gates.
            add_intermediate_term(self._resized_inputs[-2])
            add_intermediate_term(self._resized_inputs[-1])
        else:
            assert len(self.inputs) % FULL_ADDER_INPUT_COUNT == 0

        return intermediate_terms, m


class AddReduce(AddReduceSingle):
    """Recursively Add list of numbers together.

    :attribute inputs: input ``Signal``s to be summed. Modification not
        supported, except for by ``Signal.eq``.
    :attribute register_levels: List of nesting levels that should have
        pipeline registers.
    :attribute output: output sum.
    :attribute partition_points: the input partition points. Modification not
        supported, except for by ``Signal.eq``.
    """

    def __init__(self, inputs, output_width, register_levels, partition_points):
        """Create an ``AddReduce``.

        :param inputs: input ``Signal``s to be summed.
        :param output_width: bit-width of ``output``.
        :param register_levels: List of nesting levels that should have
            pipeline registers.
        :param partition_points: the input partition points.
        """
        AddReduceSingle.__init__(self, inputs, output_width, register_levels,
                                 partition_points)

    def next_register_levels(self):
        """``Iterable`` of ``register_levels`` for next recursive level."""
        for level in self.register_levels:
            if level > 0:
                yield level - 1

    def elaborate(self, platform):
        """Elaborate this module."""
        intermediate_terms, m = AddReduceSingle._elaborate(self, platform)
        if intermediate_terms is None:
            return m

        # recursive invocation of ``AddReduce``
        next_level = AddReduce(intermediate_terms,
                               len(self.output),
                               self.next_register_levels(),
                               self._reg_partition_points)
        m.submodules.next_level = next_level
        m.d.comb += self.output.eq(next_level.output)
        return m


OP_MUL_LOW = 0
OP_MUL_SIGNED_HIGH = 1
OP_MUL_SIGNED_UNSIGNED_HIGH = 2  # a is signed, b is unsigned
OP_MUL_UNSIGNED_HIGH = 3


def get_term(value, shift=0, enabled=None):
    if enabled is not None:
        value = Mux(enabled, value, 0)
    if shift > 0:
        value = Cat(Repl(C(0, 1), shift), value)
    else:
        assert shift == 0
    return value


class ProductTerm(Elaboratable):
    """ this class creates a single product term (a[..]*b[..]).
        it has a design flaw in that is the *output* that is selected,
        where the multiplication(s) are combinatorially generated
        all the time.
    """

    def __init__(self, width, twidth, pbwid, a_index, b_index):
        self.a_index = a_index
        self.b_index = b_index
        shift = 8 * (self.a_index + self.b_index)
        self.pwidth = width
        self.twidth = twidth
        self.width = width*2
        self.shift = shift

        self.ti = Signal(self.width, reset_less=True)
        self.term = Signal(twidth, reset_less=True)
        self.a = Signal(twidth//2, reset_less=True)
        self.b = Signal(twidth//2, reset_less=True)
        self.pb_en = Signal(pbwid, reset_less=True)

        self.tl = tl = []
        min_index = min(self.a_index, self.b_index)
        max_index = max(self.a_index, self.b_index)
        for i in range(min_index, max_index):
            tl.append(self.pb_en[i])
        name = "te_%d_%d" % (self.a_index, self.b_index)
        if len(tl) > 0:
            term_enabled = Signal(name=name, reset_less=True)
        else:
            term_enabled = None
        self.enabled = term_enabled
        self.term.name = "term_%d_%d" % (a_index, b_index) # rename

    def elaborate(self, platform):

        m = Module()
        if self.enabled is not None:
            m.d.comb += self.enabled.eq(~(Cat(*self.tl).bool()))

        bsa = Signal(self.width, reset_less=True)
        bsb = Signal(self.width, reset_less=True)
        a_index, b_index = self.a_index, self.b_index
        pwidth = self.pwidth
        m.d.comb += bsa.eq(self.a.bit_select(a_index * pwidth, pwidth))
        m.d.comb += bsb.eq(self.b.bit_select(b_index * pwidth, pwidth))
        m.d.comb += self.ti.eq(bsa * bsb)
        m.d.comb += self.term.eq(get_term(self.ti, self.shift, self.enabled))
        """
        #TODO: sort out width issues, get inputs a/b switched on/off.
        #data going into Muxes is 1/2 the required width

        pwidth = self.pwidth
        width = self.width
        bsa = Signal(self.twidth//2, reset_less=True)
        bsb = Signal(self.twidth//2, reset_less=True)
        asel = Signal(width, reset_less=True)
        bsel = Signal(width, reset_less=True)
        a_index, b_index = self.a_index, self.b_index
        m.d.comb += asel.eq(self.a.bit_select(a_index * pwidth, pwidth))
        m.d.comb += bsel.eq(self.b.bit_select(b_index * pwidth, pwidth))
        m.d.comb += bsa.eq(get_term(asel, self.shift, self.enabled))
        m.d.comb += bsb.eq(get_term(bsel, self.shift, self.enabled))
        m.d.comb += self.ti.eq(bsa * bsb)
        m.d.comb += self.term.eq(self.ti)
        """

        return m


class ProductTerms(Elaboratable):
    """ creates a bank of product terms.  also performs the actual bit-selection
        this class is to be wrapped with a for-loop on the "a" operand.
        it creates a second-level for-loop on the "b" operand.
    """
    def __init__(self, width, twidth, pbwid, a_index, blen):
        self.a_index = a_index
        self.blen = blen
        self.pwidth = width
        self.twidth = twidth
        self.pbwid = pbwid
        self.a = Signal(twidth//2, reset_less=True)
        self.b = Signal(twidth//2, reset_less=True)
        self.pb_en = Signal(pbwid, reset_less=True)
        self.terms = [Signal(twidth, name="term%d"%i, reset_less=True) \
                            for i in range(blen)]

    def elaborate(self, platform):

        m = Module()

        for b_index in range(self.blen):
            t = ProductTerm(self.pwidth, self.twidth, self.pbwid,
                            self.a_index, b_index)
            setattr(m.submodules, "term_%d" % b_index, t)

            m.d.comb += t.a.eq(self.a)
            m.d.comb += t.b.eq(self.b)
            m.d.comb += t.pb_en.eq(self.pb_en)

            m.d.comb += self.terms[b_index].eq(t.term)

        return m

class LSBNegTerm(Elaboratable):

    def __init__(self, bit_width):
        self.bit_width = bit_width
        self.part = Signal(reset_less=True)
        self.signed = Signal(reset_less=True)
        self.op = Signal(bit_width, reset_less=True)
        self.msb = Signal(reset_less=True)
        self.nt = Signal(bit_width*2, reset_less=True)
        self.nl = Signal(bit_width*2, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        bit_wid = self.bit_width
        ext = Repl(0, bit_wid) # extend output to HI part

        # determine sign of each incoming number *in this partition*
        enabled = Signal(reset_less=True)
        m.d.comb += enabled.eq(self.part & self.msb & self.signed)

        # for 8-bit values: form a * 0xFF00 by using -a * 0x100, the
        # negation operation is split into a bitwise not and a +1.
        # likewise for 16, 32, and 64-bit values.

        # width-extended 1s complement if a is signed, otherwise zero
        comb += self.nt.eq(Mux(enabled, Cat(ext, ~self.op), 0))

        # add 1 if signed, otherwise add zero
        comb += self.nl.eq(Cat(ext, enabled, Repl(0, bit_wid-1)))

        return m


class Part(Elaboratable):
    """ a key class which, depending on the partitioning, will determine
        what action to take when parts of the output are signed or unsigned.

        this requires 2 pieces of data *per operand, per partition*:
        whether the MSB is HI/LO (per partition!), and whether a signed
        or unsigned operation has been *requested*.

        once that is determined, signed is basically carried out
        by splitting 2's complement into 1's complement plus one.
        1's complement is just a bit-inversion.

        the extra terms - as separate terms - are then thrown at the
        AddReduce alongside the multiplication part-results.
    """
    def __init__(self, width, n_parts, n_levels, pbwid):

        # inputs
        self.a = Signal(64)
        self.b = Signal(64)
        self.a_signed = [Signal(name=f"a_signed_{i}") for i in range(8)]
        self.b_signed = [Signal(name=f"_b_signed_{i}") for i in range(8)]
        self.pbs = Signal(pbwid, reset_less=True)

        # outputs
        self.parts = [Signal(name=f"part_{i}") for i in range(n_parts)]
        self.delayed_parts = [
            [Signal(name=f"delayed_part_{delay}_{i}")
             for i in range(n_parts)]
                for delay in range(n_levels)]
        # XXX REALLY WEIRD BUG - have to take a copy of the last delayed_parts
        self.dplast = [Signal(name=f"dplast_{i}")
                         for i in range(n_parts)]

        self.not_a_term = Signal(width)
        self.neg_lsb_a_term = Signal(width)
        self.not_b_term = Signal(width)
        self.neg_lsb_b_term = Signal(width)

    def elaborate(self, platform):
        m = Module()

        pbs, parts, delayed_parts = self.pbs, self.parts, self.delayed_parts
        # negated-temporary copy of partition bits
        npbs = Signal.like(pbs, reset_less=True)
        m.d.comb += npbs.eq(~pbs)
        byte_count = 8 // len(parts)
        for i in range(len(parts)):
            pbl = []
            pbl.append(npbs[i * byte_count - 1])
            for j in range(i * byte_count, (i + 1) * byte_count - 1):
                pbl.append(pbs[j])
            pbl.append(npbs[(i + 1) * byte_count - 1])
            value = Signal(len(pbl), name="value_%di" % i, reset_less=True)
            m.d.comb += value.eq(Cat(*pbl))
            m.d.comb += parts[i].eq(~(value).bool())
            m.d.comb += delayed_parts[0][i].eq(parts[i])
            m.d.sync += [delayed_parts[j + 1][i].eq(delayed_parts[j][i])
                         for j in range(len(delayed_parts)-1)]
            m.d.comb += self.dplast[i].eq(delayed_parts[-1][i])

        not_a_term, neg_lsb_a_term, not_b_term, neg_lsb_b_term = \
                self.not_a_term, self.neg_lsb_a_term, \
                self.not_b_term, self.neg_lsb_b_term

        byte_width = 8 // len(parts) # byte width
        bit_wid = 8 * byte_width     # bit width
        nat, nbt, nla, nlb = [], [], [], []
        for i in range(len(parts)):
            # work out bit-inverted and +1 term for a.
            pa = LSBNegTerm(bit_wid)
            setattr(m.submodules, "lnt_%d_a_%d" % (bit_wid, i), pa)
            m.d.comb += pa.part.eq(parts[i])
            m.d.comb += pa.op.eq(self.a.bit_select(bit_wid * i, bit_wid))
            m.d.comb += pa.signed.eq(self.b_signed[i * byte_width]) # yes b
            m.d.comb += pa.msb.eq(self.b[(i + 1) * bit_wid - 1]) # really, b
            nat.append(pa.nt)
            nla.append(pa.nl)

            # work out bit-inverted and +1 term for b
            pb = LSBNegTerm(bit_wid)
            setattr(m.submodules, "lnt_%d_b_%d" % (bit_wid, i), pb)
            m.d.comb += pb.part.eq(parts[i])
            m.d.comb += pb.op.eq(self.b.bit_select(bit_wid * i, bit_wid))
            m.d.comb += pb.signed.eq(self.a_signed[i * byte_width]) # yes a
            m.d.comb += pb.msb.eq(self.a[(i + 1) * bit_wid - 1]) # really, a
            nbt.append(pb.nt)
            nlb.append(pb.nl)

        # concatenate together and return all 4 results.
        m.d.comb += [not_a_term.eq(Cat(*nat)),
                     not_b_term.eq(Cat(*nbt)),
                     neg_lsb_a_term.eq(Cat(*nla)),
                     neg_lsb_b_term.eq(Cat(*nlb)),
                    ]

        return m


class IntermediateOut(Elaboratable):
    """ selects the HI/LO part of the multiplication, for a given bit-width
        the output is also reconstructed in its SIMD (partition) lanes.
    """
    def __init__(self, width, out_wid, n_parts):
        self.width = width
        self.n_parts = n_parts
        self.delayed_part_ops = [Signal(2, name="dpop%d" % i, reset_less=True)
                                     for i in range(8)]
        self.intermed = Signal(out_wid, reset_less=True)
        self.output = Signal(out_wid//2, reset_less=True)

    def elaborate(self, platform):
        m = Module()

        ol = []
        w = self.width
        sel = w // 8
        for i in range(self.n_parts):
            op = Signal(w, reset_less=True, name="op%d_%d" % (w, i))
            m.d.comb += op.eq(
                Mux(self.delayed_part_ops[sel * i] == OP_MUL_LOW,
                    self.intermed.bit_select(i * w*2, w),
                    self.intermed.bit_select(i * w*2 + w, w)))
            ol.append(op)
        m.d.comb += self.output.eq(Cat(*ol))

        return m


class FinalOut(Elaboratable):
    """ selects the final output based on the partitioning.

        each byte is selectable independently, i.e. it is possible
        that some partitions requested 8-bit computation whilst others
        requested 16 or 32 bit.
    """
    def __init__(self, out_wid):
        # inputs
        self.d8 = [Signal(name=f"d8_{i}", reset_less=True) for i in range(8)]
        self.d16 = [Signal(name=f"d16_{i}", reset_less=True) for i in range(4)]
        self.d32 = [Signal(name=f"d32_{i}", reset_less=True) for i in range(2)]

        self.i8 = Signal(out_wid, reset_less=True)
        self.i16 = Signal(out_wid, reset_less=True)
        self.i32 = Signal(out_wid, reset_less=True)
        self.i64 = Signal(out_wid, reset_less=True)

        # output
        self.out = Signal(out_wid, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        ol = []
        for i in range(8):
            # select one of the outputs: d8 selects i8, d16 selects i16
            # d32 selects i32, and the default is i64.
            # d8 and d16 are ORed together in the first Mux
            # then the 2nd selects either i8 or i16.
            # if neither d8 nor d16 are set, d32 selects either i32 or i64.
            op = Signal(8, reset_less=True, name="op_%d" % i)
            m.d.comb += op.eq(
                Mux(self.d8[i] | self.d16[i // 2],
                    Mux(self.d8[i], self.i8.bit_select(i * 8, 8),
                                     self.i16.bit_select(i * 8, 8)),
                    Mux(self.d32[i // 4], self.i32.bit_select(i * 8, 8),
                                          self.i64.bit_select(i * 8, 8))))
            ol.append(op)
        m.d.comb += self.out.eq(Cat(*ol))
        return m


class OrMod(Elaboratable):
    """ ORs four values together in a hierarchical tree
    """
    def __init__(self, wid):
        self.wid = wid
        self.orin = [Signal(wid, name="orin%d" % i, reset_less=True)
                     for i in range(4)]
        self.orout = Signal(wid, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        or1 = Signal(self.wid, reset_less=True)
        or2 = Signal(self.wid, reset_less=True)
        m.d.comb += or1.eq(self.orin[0] | self.orin[1])
        m.d.comb += or2.eq(self.orin[2] | self.orin[3])
        m.d.comb += self.orout.eq(or1 | or2)

        return m


class Signs(Elaboratable):
    """ determines whether a or b are signed numbers
        based on the required operation type (OP_MUL_*)
    """

    def __init__(self):
        self.part_ops = Signal(2, reset_less=True)
        self.a_signed = Signal(reset_less=True)
        self.b_signed = Signal(reset_less=True)

    def elaborate(self, platform):

        m = Module()

        asig = self.part_ops != OP_MUL_UNSIGNED_HIGH
        bsig = (self.part_ops == OP_MUL_LOW) \
                    | (self.part_ops == OP_MUL_SIGNED_HIGH)
        m.d.comb += self.a_signed.eq(asig)
        m.d.comb += self.b_signed.eq(bsig)

        return m


class Mul8_16_32_64(Elaboratable):
    """Signed/Unsigned 8/16/32/64-bit partitioned integer multiplier.

    Supports partitioning into any combination of 8, 16, 32, and 64-bit
    partitions on naturally-aligned boundaries. Supports the operation being
    set for each partition independently.

    :attribute part_pts: the input partition points. Has a partition point at
        multiples of 8 in 0 < i < 64. Each partition point's associated
        ``Value`` is a ``Signal``. Modification not supported, except for by
        ``Signal.eq``.
    :attribute part_ops: the operation for each byte. The operation for a
        particular partition is selected by assigning the selected operation
        code to each byte in the partition. The allowed operation codes are:

        :attribute OP_MUL_LOW: the LSB half of the product. Equivalent to
            RISC-V's `mul` instruction.
        :attribute OP_MUL_SIGNED_HIGH: the MSB half of the product where both
            ``a`` and ``b`` are signed. Equivalent to RISC-V's `mulh`
            instruction.
        :attribute OP_MUL_SIGNED_UNSIGNED_HIGH: the MSB half of the product
            where ``a`` is signed and ``b`` is unsigned. Equivalent to RISC-V's
            `mulhsu` instruction.
        :attribute OP_MUL_UNSIGNED_HIGH: the MSB half of the product where both
            ``a`` and ``b`` are unsigned. Equivalent to RISC-V's `mulhu`
            instruction.
    """

    def __init__(self, register_levels=()):
        """ register_levels: specifies the points in the cascade at which
            flip-flops are to be inserted.
        """

        # parameter(s)
        self.register_levels = list(register_levels)

        # inputs
        self.part_pts = PartitionPoints()
        for i in range(8, 64, 8):
            self.part_pts[i] = Signal(name=f"part_pts_{i}")
        self.part_ops = [Signal(2, name=f"part_ops_{i}") for i in range(8)]
        self.a = Signal(64)
        self.b = Signal(64)

        # intermediates (needed for unit tests)
        self._intermediate_output = Signal(128)

        # output
        self.output = Signal(64)

    def _part_byte(self, index):
        if index == -1 or index == 7:
            return C(True, 1)
        assert index >= 0 and index < 8
        return self.part_pts[index * 8 + 8]

    def elaborate(self, platform):
        m = Module()

        # collect part-bytes
        pbs = Signal(8, reset_less=True)
        tl = []
        for i in range(8):
            pb = Signal(name="pb%d" % i, reset_less=True)
            m.d.comb += pb.eq(self._part_byte(i))
            tl.append(pb)
        m.d.comb += pbs.eq(Cat(*tl))

        # local variables
        signs = []
        for i in range(8):
            s = Signs()
            signs.append(s)
            setattr(m.submodules, "signs%d" % i, s)
            m.d.comb += s.part_ops.eq(self.part_ops[i])

        delayed_part_ops = [
            [Signal(2, name=f"_delayed_part_ops_{delay}_{i}")
             for i in range(8)]
            for delay in range(1 + len(self.register_levels))]
        for i in range(len(self.part_ops)):
            m.d.comb += delayed_part_ops[0][i].eq(self.part_ops[i])
            m.d.sync += [delayed_part_ops[j + 1][i].eq(delayed_part_ops[j][i])
                         for j in range(len(self.register_levels))]

        n_levels = len(self.register_levels)+1
        m.submodules.part_8 = part_8 = Part(128, 8, n_levels, 8)
        m.submodules.part_16 = part_16 = Part(128, 4, n_levels, 8)
        m.submodules.part_32 = part_32 = Part(128, 2, n_levels, 8)
        m.submodules.part_64 = part_64 = Part(128, 1, n_levels, 8)
        nat_l, nbt_l, nla_l, nlb_l = [], [], [], []
        for mod in [part_8, part_16, part_32, part_64]:
            m.d.comb += mod.a.eq(self.a)
            m.d.comb += mod.b.eq(self.b)
            for i in range(len(signs)):
                m.d.comb += mod.a_signed[i].eq(signs[i].a_signed)
                m.d.comb += mod.b_signed[i].eq(signs[i].b_signed)
            m.d.comb += mod.pbs.eq(pbs)
            nat_l.append(mod.not_a_term)
            nbt_l.append(mod.not_b_term)
            nla_l.append(mod.neg_lsb_a_term)
            nlb_l.append(mod.neg_lsb_b_term)

        terms = []

        for a_index in range(8):
            t = ProductTerms(8, 128, 8, a_index, 8)
            setattr(m.submodules, "terms_%d" % a_index, t)

            m.d.comb += t.a.eq(self.a)
            m.d.comb += t.b.eq(self.b)
            m.d.comb += t.pb_en.eq(pbs)

            for term in t.terms:
                terms.append(term)

        # it's fine to bitwise-or data together since they are never enabled
        # at the same time
        m.submodules.nat_or = nat_or = OrMod(128)
        m.submodules.nbt_or = nbt_or = OrMod(128)
        m.submodules.nla_or = nla_or = OrMod(128)
        m.submodules.nlb_or = nlb_or = OrMod(128)
        for l, mod in [(nat_l, nat_or),
                             (nbt_l, nbt_or),
                             (nla_l, nla_or),
                             (nlb_l, nlb_or)]:
            for i in range(len(l)):
                m.d.comb += mod.orin[i].eq(l[i])
            terms.append(mod.orout)

        expanded_part_pts = PartitionPoints()
        for i, v in self.part_pts.items():
            signal = Signal(name=f"expanded_part_pts_{i*2}", reset_less=True)
            expanded_part_pts[i * 2] = signal
            m.d.comb += signal.eq(v)

        add_reduce = AddReduce(terms,
                               128,
                               self.register_levels,
                               expanded_part_pts)
        m.submodules.add_reduce = add_reduce
        m.d.comb += self._intermediate_output.eq(add_reduce.output)
        # create _output_64
        m.submodules.io64 = io64 = IntermediateOut(64, 128, 1)
        m.d.comb += io64.intermed.eq(self._intermediate_output)
        for i in range(8):
            m.d.comb += io64.delayed_part_ops[i].eq(delayed_part_ops[-1][i])

        # create _output_32
        m.submodules.io32 = io32 = IntermediateOut(32, 128, 2)
        m.d.comb += io32.intermed.eq(self._intermediate_output)
        for i in range(8):
            m.d.comb += io32.delayed_part_ops[i].eq(delayed_part_ops[-1][i])

        # create _output_16
        m.submodules.io16 = io16 = IntermediateOut(16, 128, 4)
        m.d.comb += io16.intermed.eq(self._intermediate_output)
        for i in range(8):
            m.d.comb += io16.delayed_part_ops[i].eq(delayed_part_ops[-1][i])

        # create _output_8
        m.submodules.io8 = io8 = IntermediateOut(8, 128, 8)
        m.d.comb += io8.intermed.eq(self._intermediate_output)
        for i in range(8):
            m.d.comb += io8.delayed_part_ops[i].eq(delayed_part_ops[-1][i])

        # final output
        m.submodules.finalout = finalout = FinalOut(64)
        for i in range(len(part_8.delayed_parts[-1])):
            m.d.comb += finalout.d8[i].eq(part_8.dplast[i])
        for i in range(len(part_16.delayed_parts[-1])):
            m.d.comb += finalout.d16[i].eq(part_16.dplast[i])
        for i in range(len(part_32.delayed_parts[-1])):
            m.d.comb += finalout.d32[i].eq(part_32.dplast[i])
        m.d.comb += finalout.i8.eq(io8.output)
        m.d.comb += finalout.i16.eq(io16.output)
        m.d.comb += finalout.i32.eq(io32.output)
        m.d.comb += finalout.i64.eq(io64.output)
        m.d.comb += self.output.eq(finalout.out)

        return m


if __name__ == "__main__":
    m = Mul8_16_32_64()
    main(m, ports=[m.a,
                   m.b,
                   m._intermediate_output,
                   m.output,
                   *m.part_ops,
                   *m.part_pts.values()])

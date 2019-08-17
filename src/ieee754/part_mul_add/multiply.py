# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information
"""Integer Multiplication."""

from nmigen import Signal, Module, Value, Elaboratable, Cat, C, Mux, Repl
from nmigen.hdl.ast import Assign
from abc import ABCMeta, abstractmethod
from nmigen.cli import main


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


class PartitionedAdder(Elaboratable):
    """Partitioned Adder.

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
        self._expanded_a = Signal(expanded_width)
        self._expanded_b = Signal(expanded_width)
        self._expanded_output = Signal(expanded_width)

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()
        expanded_index = 0
        # store bits in a list, use Cat later.  graphviz is much cleaner
        al = []
        bl = []
        ol = []
        ea = []
        eb = []
        eo = []
        # partition points are "breaks" (extra zeros) in what would otherwise
        # be a massive long add.
        for i in range(self.width):
            if i in self.partition_points:
                # add extra bit set to 0 + 0 for enabled partition points
                # and 1 + 0 for disabled partition points
                ea.append(self._expanded_a[expanded_index])
                al.append(~self.partition_points[i])
                eb.append(self._expanded_b[expanded_index])
                bl.append(C(0))
                expanded_index += 1
            ea.append(self._expanded_a[expanded_index])
            al.append(self.a[i])
            eb.append(self._expanded_b[expanded_index])
            bl.append(self.b[i])
            eo.append(self._expanded_output[expanded_index])
            ol.append(self.output[i])
            expanded_index += 1
        # combine above using Cat
        m.d.comb += Cat(*ea).eq(Cat(*al))
        m.d.comb += Cat(*eb).eq(Cat(*bl))
        m.d.comb += Cat(*ol).eq(Cat(*eo))
        # use only one addition to take advantage of look-ahead carry and
        # special hardware on FPGAs
        m.d.comb += self._expanded_output.eq(
            self._expanded_a + self._expanded_b)
        return m


FULL_ADDER_INPUT_COUNT = 3


class AddReduce(Elaboratable):
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

    def next_register_levels(self):
        """``Iterable`` of ``register_levels`` for next recursive level."""
        for level in self.register_levels:
            if level > 0:
                yield level - 1

    @staticmethod
    def full_adder_groups(input_count):
        """Get ``inputs`` indices for which a full adder should be built."""
        return range(0,
                     input_count - FULL_ADDER_INPUT_COUNT + 1,
                     FULL_ADDER_INPUT_COUNT)

    def elaborate(self, platform):
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

        groups = AddReduce.full_adder_groups(len(self.inputs))
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
            return m
        # go on to handle recursive case
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
            adder_i = FullAdder(len(self.output))
            setattr(m.submodules, f"adder_{i}", adder_i)
            m.d.comb += adder_i.in0.eq(self._resized_inputs[i])
            m.d.comb += adder_i.in1.eq(self._resized_inputs[i + 1])
            m.d.comb += adder_i.in2.eq(self._resized_inputs[i + 2])
            add_intermediate_term(adder_i.sum)
            shifted_carry = adder_i.carry << 1
            # mask out carry bits to prevent carries between partitions
            add_intermediate_term((adder_i.carry << 1) & part_mask)
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

    def __init__(self, register_levels= ()):
        self.part_pts = PartitionPoints()
        for i in range(8, 64, 8):
            self.part_pts[i] = Signal(name=f"part_pts_{i}")
        self.part_ops = [Signal(2, name=f"part_ops_{i}") for i in range(8)]
        self.a = Signal(64)
        self.b = Signal(64)
        self.output = Signal(64)
        self.register_levels = list(register_levels)
        self._intermediate_output = Signal(128)
        self._delayed_part_ops = [
            [Signal(2, name=f"_delayed_part_ops_{delay}_{i}")
             for i in range(8)]
            for delay in range(1 + len(self.register_levels))]
        self._part_8 = [Signal(name=f"_part_8_{i}") for i in range(8)]
        self._part_16 = [Signal(name=f"_part_16_{i}") for i in range(4)]
        self._part_32 = [Signal(name=f"_part_32_{i}") for i in range(2)]
        self._part_64 = [Signal(name=f"_part_64")]
        self._delayed_part_8 = [
            [Signal(name=f"_delayed_part_8_{delay}_{i}")
             for i in range(8)]
            for delay in range(1 + len(self.register_levels))]
        self._delayed_part_16 = [
            [Signal(name=f"_delayed_part_16_{delay}_{i}")
             for i in range(4)]
            for delay in range(1 + len(self.register_levels))]
        self._delayed_part_32 = [
            [Signal(name=f"_delayed_part_32_{delay}_{i}")
             for i in range(2)]
            for delay in range(1 + len(self.register_levels))]
        self._delayed_part_64 = [
            [Signal(name=f"_delayed_part_64_{delay}")]
            for delay in range(1 + len(self.register_levels))]
        self._output_64 = Signal(64)
        self._output_32 = Signal(64)
        self._output_16 = Signal(64)
        self._output_8 = Signal(64)
        self._a_signed = [Signal(name=f"_a_signed_{i}") for i in range(8)]
        self._b_signed = [Signal(name=f"_b_signed_{i}") for i in range(8)]
        self._not_a_term_8 = Signal(128)
        self._neg_lsb_a_term_8 = Signal(128)
        self._not_b_term_8 = Signal(128)
        self._neg_lsb_b_term_8 = Signal(128)
        self._not_a_term_16 = Signal(128)
        self._neg_lsb_a_term_16 = Signal(128)
        self._not_b_term_16 = Signal(128)
        self._neg_lsb_b_term_16 = Signal(128)
        self._not_a_term_32 = Signal(128)
        self._neg_lsb_a_term_32 = Signal(128)
        self._not_b_term_32 = Signal(128)
        self._neg_lsb_b_term_32 = Signal(128)
        self._not_a_term_64 = Signal(128)
        self._neg_lsb_a_term_64 = Signal(128)
        self._not_b_term_64 = Signal(128)
        self._neg_lsb_b_term_64 = Signal(128)

    def _part_byte(self, index):
        if index == -1 or index == 7:
            return C(True, 1)
        assert index >= 0 and index < 8
        return self.part_pts[index * 8 + 8]

    def elaborate(self, platform):
        m = Module()

        for i in range(len(self.part_ops)):
            m.d.comb += self._delayed_part_ops[0][i].eq(self.part_ops[i])
            m.d.sync += [self._delayed_part_ops[j + 1][i]
                         .eq(self._delayed_part_ops[j][i])
                         for j in range(len(self.register_levels))]

        def add_intermediate_value(value):
            intermediate_value = Signal(len(value), reset_less=True)
            m.d.comb += intermediate_value.eq(value)
            return intermediate_value

        for parts, delayed_parts in [(self._part_64, self._delayed_part_64),
                                     (self._part_32, self._delayed_part_32),
                                     (self._part_16, self._delayed_part_16),
                                     (self._part_8, self._delayed_part_8)]:
            byte_count = 8 // len(parts)
            for i in range(len(parts)):
                pb = self._part_byte(i * byte_count - 1)
                value = add_intermediate_value(pb)
                for j in range(i * byte_count, (i + 1) * byte_count - 1):
                    pb = add_intermediate_value(~self._part_byte(j))
                    value = add_intermediate_value(value & pb)
                pb = self._part_byte((i + 1) * byte_count - 1)
                value = add_intermediate_value(value & pb)
                m.d.comb += parts[i].eq(value)
                m.d.comb += delayed_parts[0][i].eq(parts[i])
                m.d.sync += [delayed_parts[j + 1][i].eq(delayed_parts[j][i])
                             for j in range(len(self.register_levels))]

        products = [[
                Signal(16, name=f"products_{i}_{j}", reset_less=True)
                for j in range(8)]
            for i in range(8)]

        for a_index in range(8):
            for b_index in range(8):
                a = self.a.part(a_index * 8, 8)
                b = self.b.part(b_index * 8, 8)
                m.d.comb += products[a_index][b_index].eq(a * b)

        terms = []

        def add_term(value, shift=0, enabled=None):
            term = Signal(128, reset_less=True)
            terms.append(term)
            if enabled is not None:
                value = Mux(enabled, value, 0)
            if shift > 0:
                value = Cat(Repl(C(0, 1), shift), value)
            else:
                assert shift == 0
            m.d.comb += term.eq(value)

        for a_index in range(8):
            for b_index in range(8):
                tl = []
                min_index = min(a_index, b_index)
                max_index = max(a_index, b_index)
                for i in range(min_index, max_index):
                    pbs = Signal(reset_less=True)
                    m.d.comb += pbs.eq(self._part_byte(i))
                    tl.append(pbs)
                name = "te_%d_%d" % (a_index, b_index)
                term_enabled = Signal(name=name, reset_less=True)
                m.d.comb += term_enabled.eq(~(Cat(*tl).bool()))
                add_term(products[a_index][b_index],
                         8 * (a_index + b_index),
                         term_enabled)

        for i in range(8):
            a_signed = self.part_ops[i] != OP_MUL_UNSIGNED_HIGH
            b_signed = (self.part_ops[i] == OP_MUL_LOW) \
                | (self.part_ops[i] == OP_MUL_SIGNED_HIGH)
            m.d.comb += self._a_signed[i].eq(a_signed)
            m.d.comb += self._b_signed[i].eq(b_signed)

        # it's fine to bitwise-or these together since they are never enabled
        # at the same time
        add_term(self._not_a_term_8 | self._not_a_term_16
                 | self._not_a_term_32 | self._not_a_term_64)
        add_term(self._neg_lsb_a_term_8 | self._neg_lsb_a_term_16
                 | self._neg_lsb_a_term_32 | self._neg_lsb_a_term_64)
        add_term(self._not_b_term_8 | self._not_b_term_16
                 | self._not_b_term_32 | self._not_b_term_64)
        add_term(self._neg_lsb_b_term_8 | self._neg_lsb_b_term_16
                 | self._neg_lsb_b_term_32 | self._neg_lsb_b_term_64)

        for not_a_term, \
            neg_lsb_a_term, \
            not_b_term, \
            neg_lsb_b_term, \
            parts in [
                (self._not_a_term_8,
                 self._neg_lsb_a_term_8,
                 self._not_b_term_8,
                 self._neg_lsb_b_term_8,
                 self._part_8),
                (self._not_a_term_16,
                 self._neg_lsb_a_term_16,
                 self._not_b_term_16,
                 self._neg_lsb_b_term_16,
                 self._part_16),
                (self._not_a_term_32,
                 self._neg_lsb_a_term_32,
                 self._not_b_term_32,
                 self._neg_lsb_b_term_32,
                 self._part_32),
                (self._not_a_term_64,
                 self._neg_lsb_a_term_64,
                 self._not_b_term_64,
                 self._neg_lsb_b_term_64,
                 self._part_64),
                ]:
            byte_width = 8 // len(parts)
            bit_width = 8 * byte_width
            for i in range(len(parts)):
                ae = parts[i] & self.a[(i + 1) * bit_width - 1] \
                    & self._a_signed[i * byte_width]
                be = parts[i] & self.b[(i + 1) * bit_width - 1] \
                    & self._b_signed[i * byte_width]
                a_enabled = Signal(name="a_enabled_%d" % i, reset_less=True)
                b_enabled = Signal(name="b_enabled_%d" % i, reset_less=True)
                m.d.comb += a_enabled.eq(ae)
                m.d.comb += b_enabled.eq(be)

                # for 8-bit values: form a * 0xFF00 by using -a * 0x100, the
                # negation operation is split into a bitwise not and a +1.
                # likewise for 16, 32, and 64-bit values.
                m.d.comb += [
                    not_a_term.part(bit_width * 2 * i, bit_width * 2)
                    .eq(Mux(a_enabled,
                            Cat(Repl(0, bit_width),
                                ~self.a.part(bit_width * i, bit_width)),
                            0)),

                    neg_lsb_a_term.part(bit_width * 2 * i, bit_width * 2)
                    .eq(Cat(Repl(0, bit_width), a_enabled)),

                    not_b_term.part(bit_width * 2 * i, bit_width * 2)
                    .eq(Mux(b_enabled,
                            Cat(Repl(0, bit_width),
                                ~self.b.part(bit_width * i, bit_width)),
                            0)),

                    neg_lsb_b_term.part(bit_width * 2 * i, bit_width * 2)
                    .eq(Cat(Repl(0, bit_width), b_enabled))]

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
        m.d.comb += self._output_64.eq(
            Mux(self._delayed_part_ops[-1][0] == OP_MUL_LOW,
                self._intermediate_output.part(0, 64),
                self._intermediate_output.part(64, 64)))

        # create _output_32
        ol = []
        for i in range(2):
            op = Signal(32, reset_less=True, name="op32_%d" % i)
            m.d.comb += op.eq(
                Mux(self._delayed_part_ops[-1][4 * i] == OP_MUL_LOW,
                    self._intermediate_output.part(i * 64, 32),
                    self._intermediate_output.part(i * 64 + 32, 32)))
            ol.append(op)
        m.d.comb += self._output_32.eq(Cat(*ol))

        # create _output_16
        ol = []
        for i in range(4):
            op = Signal(16, reset_less=True, name="op16_%d" % i)
            m.d.comb += op.eq(
                Mux(self._delayed_part_ops[-1][2 * i] == OP_MUL_LOW,
                    self._intermediate_output.part(i * 32, 16),
                    self._intermediate_output.part(i * 32 + 16, 16)))
            ol.append(op)
        m.d.comb += self._output_16.eq(Cat(*ol))

        # create _output_8
        ol = []
        for i in range(8):
            op = Signal(8, reset_less=True, name="op8_%d" % i)
            m.d.comb += op.eq(
                Mux(self._delayed_part_ops[-1][i] == OP_MUL_LOW,
                    self._intermediate_output.part(i * 16, 8),
                    self._intermediate_output.part(i * 16 + 8, 8)))
            ol.append(op)
        m.d.comb += self._output_8.eq(Cat(*ol))

        # final output
        ol = []
        for i in range(8):
            op = Signal(8, reset_less=True, name="op%d" % i)
            m.d.comb += op.eq(
                Mux(self._delayed_part_8[-1][i]
                    | self._delayed_part_16[-1][i // 2],
                    Mux(self._delayed_part_8[-1][i],
                        self._output_8.part(i * 8, 8),
                        self._output_16.part(i * 8, 8)),
                    Mux(self._delayed_part_32[-1][i // 4],
                        self._output_32.part(i * 8, 8),
                        self._output_64.part(i * 8, 8))))
            ol.append(op)
        m.d.comb += self.output.eq(Cat(*ol))
        return m


if __name__ == "__main__":
    m = Mul8_16_32_64()
    main(m, ports=[m.a,
                   m.b,
                   m._intermediate_output,
                   m.output,
                   *m.part_ops,
                   *m.part_pts.values()])

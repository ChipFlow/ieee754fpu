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
from ieee754.part_mul_add.adder import PartitionedAdder, MaskedFullAdder


FULL_ADDER_INPUT_COUNT = 3

class AddReduceData:

    def __init__(self, part_pts, n_inputs, output_width, n_parts):
        self.part_ops = [Signal(2, name=f"part_ops_{i}", reset_less=True)
                          for i in range(n_parts)]
        self.terms = [Signal(output_width, name=f"terms_{i}",
                              reset_less=True)
                        for i in range(n_inputs)]
        self.part_pts = part_pts.like()

    def eq_from(self, part_pts, inputs, part_ops):
        return [self.part_pts.eq(part_pts)] + \
               [self.terms[i].eq(inputs[i])
                                     for i in range(len(self.terms))] + \
               [self.part_ops[i].eq(part_ops[i])
                                     for i in range(len(self.part_ops))]

    def eq(self, rhs):
        return self.eq_from(rhs.part_pts, rhs.terms, rhs.part_ops)


class FinalReduceData:

    def __init__(self, part_pts, output_width, n_parts):
        self.part_ops = [Signal(2, name=f"part_ops_{i}", reset_less=True)
                          for i in range(n_parts)]
        self.output = Signal(output_width, reset_less=True)
        self.part_pts = part_pts.like()

    def eq_from(self, part_pts, output, part_ops):
        return [self.part_pts.eq(part_pts)] + \
               [self.output.eq(output)] + \
               [self.part_ops[i].eq(part_ops[i])
                                     for i in range(len(self.part_ops))]

    def eq(self, rhs):
        return self.eq_from(rhs.part_pts, rhs.output, rhs.part_ops)


class FinalAdd(PipeModBase):
    """ Final stage of add reduce
    """

    def __init__(self, pspec, lidx, n_inputs, partition_points,
                       partition_step=1):
        self.lidx = lidx
        self.partition_step = partition_step
        self.output_width = pspec.width * 2
        self.n_inputs = n_inputs
        self.n_parts = pspec.n_parts
        self.partition_points = PartitionPoints(partition_points)
        if not self.partition_points.fits_in_width(self.output_width):
            raise ValueError("partition_points doesn't fit in output_width")

        super().__init__(pspec, "finaladd")

    def ispec(self):
        return AddReduceData(self.partition_points, self.n_inputs,
                             self.output_width, self.n_parts)

    def ospec(self):
        return FinalReduceData(self.partition_points,
                                 self.output_width, self.n_parts)

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()

        output_width = self.output_width
        output = Signal(output_width, reset_less=True)
        if self.n_inputs == 0:
            # use 0 as the default output value
            m.d.comb += output.eq(0)
        elif self.n_inputs == 1:
            # handle single input
            m.d.comb += output.eq(self.i.terms[0])
        else:
            # base case for adding 2 inputs
            assert self.n_inputs == 2
            adder = PartitionedAdder(output_width,
                                     self.i.part_pts, self.partition_step)
            m.submodules.final_adder = adder
            m.d.comb += adder.a.eq(self.i.terms[0])
            m.d.comb += adder.b.eq(self.i.terms[1])
            m.d.comb += output.eq(adder.output)

        # create output
        m.d.comb += self.o.eq_from(self.i.part_pts, output,
                                   self.i.part_ops)

        return m


class AddReduceSingle(PipeModBase):
    """Add list of numbers together.

    :attribute inputs: input ``Signal``s to be summed. Modification not
        supported, except for by ``Signal.eq``.
    :attribute register_levels: List of nesting levels that should have
        pipeline registers.
    :attribute output: output sum.
    :attribute partition_points: the input partition points. Modification not
        supported, except for by ``Signal.eq``.
    """

    def __init__(self, pspec, lidx, n_inputs, partition_points,
                       partition_step=1):
        """Create an ``AddReduce``.

        :param inputs: input ``Signal``s to be summed.
        :param output_width: bit-width of ``output``.
        :param partition_points: the input partition points.
        """
        self.lidx = lidx
        self.partition_step = partition_step
        self.n_inputs = n_inputs
        self.n_parts = pspec.n_parts
        self.output_width = pspec.width * 2
        self.partition_points = PartitionPoints(partition_points)
        if not self.partition_points.fits_in_width(self.output_width):
            raise ValueError("partition_points doesn't fit in output_width")

        self.groups = AddReduceSingle.full_adder_groups(n_inputs)
        self.n_terms = AddReduceSingle.calc_n_inputs(n_inputs, self.groups)

        super().__init__(pspec, "addreduce_%d" % lidx)

    def ispec(self):
        return AddReduceData(self.partition_points, self.n_inputs,
                             self.output_width, self.n_parts)

    def ospec(self):
        return AddReduceData(self.partition_points, self.n_terms,
                             self.output_width, self.n_parts)

    @staticmethod
    def calc_n_inputs(n_inputs, groups):
        retval = len(groups)*2
        if n_inputs % FULL_ADDER_INPUT_COUNT == 1:
            retval += 1
        elif n_inputs % FULL_ADDER_INPUT_COUNT == 2:
            retval += 2
        else:
            assert n_inputs % FULL_ADDER_INPUT_COUNT == 0
        return retval

    @staticmethod
    def get_max_level(input_count):
        """Get the maximum level.

        All ``register_levels`` must be less than or equal to the maximum
        level.
        """
        retval = 0
        while True:
            groups = AddReduceSingle.full_adder_groups(input_count)
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

    def create_next_terms(self):
        """ create next intermediate terms, for linking up in elaborate, below
        """
        terms = []
        adders = []

        # create full adders for this recursive level.
        # this shrinks N terms to 2 * (N // 3) plus the remainder
        for i in self.groups:
            adder_i = MaskedFullAdder(self.output_width)
            adders.append((i, adder_i))
            # add both the sum and the masked-carry to the next level.
            # 3 inputs have now been reduced to 2...
            terms.append(adder_i.sum)
            terms.append(adder_i.mcarry)
        # handle the remaining inputs.
        if self.n_inputs % FULL_ADDER_INPUT_COUNT == 1:
            terms.append(self.i.terms[-1])
        elif self.n_inputs % FULL_ADDER_INPUT_COUNT == 2:
            # Just pass the terms to the next layer, since we wouldn't gain
            # anything by using a half adder since there would still be 2 terms
            # and just passing the terms to the next layer saves gates.
            terms.append(self.i.terms[-2])
            terms.append(self.i.terms[-1])
        else:
            assert self.n_inputs % FULL_ADDER_INPUT_COUNT == 0

        return terms, adders

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()

        terms, adders = self.create_next_terms()

        # copy the intermediate terms to the output
        for i, value in enumerate(terms):
            m.d.comb += self.o.terms[i].eq(value)

        # copy reg part points and part ops to output
        m.d.comb += self.o.part_pts.eq(self.i.part_pts)
        m.d.comb += [self.o.part_ops[i].eq(self.i.part_ops[i])
                                     for i in range(len(self.i.part_ops))]

        # set up the partition mask (for the adders)
        part_mask = Signal(self.output_width, reset_less=True)

        # get partition points as a mask
        mask = self.i.part_pts.as_mask(self.output_width,
                                       mul=self.partition_step)
        m.d.comb += part_mask.eq(mask)

        # add and link the intermediate term modules
        for i, (iidx, adder_i) in enumerate(adders):
            setattr(m.submodules, f"adder_{i}", adder_i)

            m.d.comb += adder_i.in0.eq(self.i.terms[iidx])
            m.d.comb += adder_i.in1.eq(self.i.terms[iidx + 1])
            m.d.comb += adder_i.in2.eq(self.i.terms[iidx + 2])
            m.d.comb += adder_i.mask.eq(part_mask)

        return m


class AddReduceInternal:
    """Iteratively Add list of numbers together.

    :attribute inputs: input ``Signal``s to be summed. Modification not
        supported, except for by ``Signal.eq``.
    :attribute register_levels: List of nesting levels that should have
        pipeline registers.
    :attribute output: output sum.
    :attribute partition_points: the input partition points. Modification not
        supported, except for by ``Signal.eq``.
    """

    def __init__(self, pspec, n_inputs, part_pts, partition_step=1):
        """Create an ``AddReduce``.

        :param inputs: input ``Signal``s to be summed.
        :param output_width: bit-width of ``output``.
        :param partition_points: the input partition points.
        """
        self.pspec = pspec
        self.n_inputs = n_inputs
        self.output_width = pspec.width * 2
        self.partition_points = part_pts
        self.partition_step = partition_step

        self.create_levels()

    def create_levels(self):
        """creates reduction levels"""

        mods = []
        partition_points = self.partition_points
        ilen = self.n_inputs
        while True:
            groups = AddReduceSingle.full_adder_groups(ilen)
            if len(groups) == 0:
                break
            lidx = len(mods)
            next_level = AddReduceSingle(self.pspec, lidx, ilen,
                                         partition_points,
                                         self.partition_step)
            mods.append(next_level)
            partition_points = next_level.i.part_pts
            ilen = len(next_level.o.terms)

        lidx = len(mods)
        next_level = FinalAdd(self.pspec, lidx, ilen,
                              partition_points, self.partition_step)
        mods.append(next_level)

        self.levels = mods


class AddReduce(AddReduceInternal, Elaboratable):
    """Recursively Add list of numbers together.

    :attribute inputs: input ``Signal``s to be summed. Modification not
        supported, except for by ``Signal.eq``.
    :attribute register_levels: List of nesting levels that should have
        pipeline registers.
    :attribute output: output sum.
    :attribute partition_points: the input partition points. Modification not
        supported, except for by ``Signal.eq``.
    """

    def __init__(self, inputs, output_width, register_levels, part_pts,
                       part_ops, partition_step=1):
        """Create an ``AddReduce``.

        :param inputs: input ``Signal``s to be summed.
        :param output_width: bit-width of ``output``.
        :param register_levels: List of nesting levels that should have
            pipeline registers.
        :param partition_points: the input partition points.
        """
        self._inputs = inputs
        self._part_pts = part_pts
        self._part_ops = part_ops
        n_parts = len(part_ops)
        self.i = AddReduceData(part_pts, len(inputs),
                             output_width, n_parts)
        AddReduceInternal.__init__(self, pspec, n_inputs, part_pts,
                                   partition_step)
        self.o = FinalReduceData(part_pts, output_width, n_parts)
        self.register_levels = register_levels

    @staticmethod
    def get_max_level(input_count):
        return AddReduceSingle.get_max_level(input_count)

    @staticmethod
    def next_register_levels(register_levels):
        """``Iterable`` of ``register_levels`` for next recursive level."""
        for level in register_levels:
            if level > 0:
                yield level - 1

    def elaborate(self, platform):
        """Elaborate this module."""
        m = Module()

        m.d.comb += self.i.eq_from(self._part_pts, self._inputs, self._part_ops)

        for i, next_level in enumerate(self.levels):
            setattr(m.submodules, "next_level%d" % i, next_level)

        i = self.i
        for idx in range(len(self.levels)):
            mcur = self.levels[idx]
            if idx in self.register_levels:
                m.d.sync += mcur.i.eq(i)
            else:
                m.d.comb += mcur.i.eq(i)
            i = mcur.o # for next loop

        # output comes from last module
        m.d.comb += self.o.eq(i)

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


class Parts(Elaboratable):

    def __init__(self, pbwid, part_pts, n_parts):
        self.pbwid = pbwid
        # inputs
        self.part_pts = PartitionPoints.like(part_pts)
        # outputs
        self.parts = [Signal(name=f"part_{i}", reset_less=True)
                      for i in range(n_parts)]

    def elaborate(self, platform):
        m = Module()

        part_pts, parts = self.part_pts, self.parts
        # collect part-bytes (double factor because the input is extended)
        pbs = Signal(self.pbwid, reset_less=True)
        tl = []
        for i in range(self.pbwid):
            pb = Signal(name="pb%d" % i, reset_less=True)
            m.d.comb += pb.eq(part_pts.part_byte(i))
            tl.append(pb)
        m.d.comb += pbs.eq(Cat(*tl))

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
            value = Signal(len(pbl), name="value_%d" % i, reset_less=True)
            m.d.comb += value.eq(Cat(*pbl))
            m.d.comb += parts[i].eq(~(value).bool())

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
    def __init__(self, part_pts, width, n_parts, pbwid):

        self.pbwid = pbwid
        self.part_pts = part_pts

        # inputs
        self.a = Signal(64, reset_less=True)
        self.b = Signal(64, reset_less=True)
        self.a_signed = [Signal(name=f"a_signed_{i}", reset_less=True)
                            for i in range(8)]
        self.b_signed = [Signal(name=f"_b_signed_{i}", reset_less=True)
                            for i in range(8)]
        self.pbs = Signal(pbwid, reset_less=True)

        # outputs
        self.parts = [Signal(name=f"part_{i}", reset_less=True)
                            for i in range(n_parts)]

        self.not_a_term = Signal(width, reset_less=True)
        self.neg_lsb_a_term = Signal(width, reset_less=True)
        self.not_b_term = Signal(width, reset_less=True)
        self.neg_lsb_b_term = Signal(width, reset_less=True)

    def elaborate(self, platform):
        m = Module()

        pbs, parts = self.pbs, self.parts
        part_pts = self.part_pts
        m.submodules.p = p = Parts(self.pbwid, part_pts, len(parts))
        m.d.comb += p.part_pts.eq(part_pts)
        parts = p.parts

        byte_count = 8 // len(parts)

        not_a_term, neg_lsb_a_term, not_b_term, neg_lsb_b_term = (
                self.not_a_term, self.neg_lsb_a_term,
                self.not_b_term, self.neg_lsb_b_term)

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
        self.part_ops = [Signal(2, name="dpop%d" % i, reset_less=True)
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
                Mux(self.part_ops[sel * i] == OP_MUL_LOW,
                    self.intermed.bit_select(i * w*2, w),
                    self.intermed.bit_select(i * w*2 + w, w)))
            ol.append(op)
        m.d.comb += self.output.eq(Cat(*ol))

        return m


class FinalOut(PipeModBase):
    """ selects the final output based on the partitioning.

        each byte is selectable independently, i.e. it is possible
        that some partitions requested 8-bit computation whilst others
        requested 16 or 32 bit.
    """
    def __init__(self, pspec, part_pts):

        self.part_pts = part_pts
        self.output_width = pspec.width * 2
        self.n_parts = pspec.n_parts
        self.out_wid = pspec.width

        super().__init__(pspec, "finalout")

    def ispec(self):
        return IntermediateData(self.part_pts, self.output_width, self.n_parts)

    def ospec(self):
        return OutputData()

    def elaborate(self, platform):
        m = Module()

        part_pts = self.part_pts
        m.submodules.p_8 = p_8 = Parts(8, part_pts, 8)
        m.submodules.p_16 = p_16 = Parts(8, part_pts, 4)
        m.submodules.p_32 = p_32 = Parts(8, part_pts, 2)
        m.submodules.p_64 = p_64 = Parts(8, part_pts, 1)

        out_part_pts = self.i.part_pts

        # temporaries
        d8 = [Signal(name=f"d8_{i}", reset_less=True) for i in range(8)]
        d16 = [Signal(name=f"d16_{i}", reset_less=True) for i in range(4)]
        d32 = [Signal(name=f"d32_{i}", reset_less=True) for i in range(2)]

        i8 = Signal(self.out_wid, reset_less=True)
        i16 = Signal(self.out_wid, reset_less=True)
        i32 = Signal(self.out_wid, reset_less=True)
        i64 = Signal(self.out_wid, reset_less=True)

        m.d.comb += p_8.part_pts.eq(out_part_pts)
        m.d.comb += p_16.part_pts.eq(out_part_pts)
        m.d.comb += p_32.part_pts.eq(out_part_pts)
        m.d.comb += p_64.part_pts.eq(out_part_pts)

        for i in range(len(p_8.parts)):
            m.d.comb += d8[i].eq(p_8.parts[i])
        for i in range(len(p_16.parts)):
            m.d.comb += d16[i].eq(p_16.parts[i])
        for i in range(len(p_32.parts)):
            m.d.comb += d32[i].eq(p_32.parts[i])
        m.d.comb += i8.eq(self.i.outputs[0])
        m.d.comb += i16.eq(self.i.outputs[1])
        m.d.comb += i32.eq(self.i.outputs[2])
        m.d.comb += i64.eq(self.i.outputs[3])

        ol = []
        for i in range(8):
            # select one of the outputs: d8 selects i8, d16 selects i16
            # d32 selects i32, and the default is i64.
            # d8 and d16 are ORed together in the first Mux
            # then the 2nd selects either i8 or i16.
            # if neither d8 nor d16 are set, d32 selects either i32 or i64.
            op = Signal(8, reset_less=True, name="op_%d" % i)
            m.d.comb += op.eq(
                Mux(d8[i] | d16[i // 2],
                    Mux(d8[i], i8.bit_select(i * 8, 8),
                               i16.bit_select(i * 8, 8)),
                    Mux(d32[i // 4], i32.bit_select(i * 8, 8),
                                      i64.bit_select(i * 8, 8))))
            ol.append(op)

        # create outputs
        m.d.comb += self.o.output.eq(Cat(*ol))
        m.d.comb += self.o.intermediate_output.eq(self.i.intermediate_output)

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


class IntermediateData:

    def __init__(self, part_pts, output_width, n_parts):
        self.part_ops = [Signal(2, name=f"part_ops_{i}", reset_less=True)
                          for i in range(n_parts)]
        self.part_pts = part_pts.like()
        self.outputs = [Signal(output_width, name="io%d" % i, reset_less=True)
                          for i in range(4)]
        # intermediates (needed for unit tests)
        self.intermediate_output = Signal(output_width)

    def eq_from(self, part_pts, outputs, intermediate_output,
                      part_ops):
        return [self.part_pts.eq(part_pts)] + \
               [self.intermediate_output.eq(intermediate_output)] + \
               [self.outputs[i].eq(outputs[i])
                                     for i in range(4)] + \
               [self.part_ops[i].eq(part_ops[i])
                                     for i in range(len(self.part_ops))]

    def eq(self, rhs):
        return self.eq_from(rhs.part_pts, rhs.outputs,
                            rhs.intermediate_output, rhs.part_ops)


class InputData:

    def __init__(self):
        self.a = Signal(64)
        self.b = Signal(64)
        self.part_pts = PartitionPoints()
        for i in range(8, 64, 8):
            self.part_pts[i] = Signal(name=f"part_pts_{i}")
        self.part_ops = [Signal(2, name=f"part_ops_{i}") for i in range(8)]

    def eq_from(self, part_pts, a, b, part_ops):
        return [self.part_pts.eq(part_pts)] + \
               [self.a.eq(a), self.b.eq(b)] + \
               [self.part_ops[i].eq(part_ops[i])
                                     for i in range(len(self.part_ops))]

    def eq(self, rhs):
        return self.eq_from(rhs.part_pts, rhs.a, rhs.b, rhs.part_ops)


class OutputData:

    def __init__(self):
        self.intermediate_output = Signal(128) # needed for unit tests
        self.output = Signal(64)

    def eq(self, rhs):
        return [self.intermediate_output.eq(rhs.intermediate_output),
                self.output.eq(rhs.output)]


class AllTerms(PipeModBase):
    """Set of terms to be added together
    """

    def __init__(self, pspec, n_inputs):
        """Create an ``AllTerms``.
        """
        self.n_inputs = n_inputs
        self.n_parts = pspec.n_parts
        self.output_width = pspec.width * 2
        super().__init__(pspec, "allterms")

    def ispec(self):
        return InputData()

    def ospec(self):
        return AddReduceData(self.i.part_pts, self.n_inputs,
                             self.output_width, self.n_parts)

    def elaborate(self, platform):
        m = Module()

        eps = self.i.part_pts

        # collect part-bytes
        pbs = Signal(8, reset_less=True)
        tl = []
        for i in range(8):
            pb = Signal(name="pb%d" % i, reset_less=True)
            m.d.comb += pb.eq(eps.part_byte(i))
            tl.append(pb)
        m.d.comb += pbs.eq(Cat(*tl))

        # local variables
        signs = []
        for i in range(8):
            s = Signs()
            signs.append(s)
            setattr(m.submodules, "signs%d" % i, s)
            m.d.comb += s.part_ops.eq(self.i.part_ops[i])

        m.submodules.part_8 = part_8 = Part(eps, 128, 8, 8)
        m.submodules.part_16 = part_16 = Part(eps, 128, 4, 8)
        m.submodules.part_32 = part_32 = Part(eps, 128, 2, 8)
        m.submodules.part_64 = part_64 = Part(eps, 128, 1, 8)
        nat_l, nbt_l, nla_l, nlb_l = [], [], [], []
        for mod in [part_8, part_16, part_32, part_64]:
            m.d.comb += mod.a.eq(self.i.a)
            m.d.comb += mod.b.eq(self.i.b)
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

            m.d.comb += t.a.eq(self.i.a)
            m.d.comb += t.b.eq(self.i.b)
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

        # copy the intermediate terms to the output
        for i, value in enumerate(terms):
            m.d.comb += self.o.terms[i].eq(value)

        # copy reg part points and part ops to output
        m.d.comb += self.o.part_pts.eq(eps)
        m.d.comb += [self.o.part_ops[i].eq(self.i.part_ops[i])
                                     for i in range(len(self.i.part_ops))]

        return m


class Intermediates(PipeModBase):
    """ Intermediate output modules
    """

    def __init__(self, pspec, part_pts):
        self.part_pts = part_pts
        self.output_width = pspec.width * 2
        self.n_parts = pspec.n_parts

        super().__init__(pspec, "intermediates")

    def ispec(self):
        return FinalReduceData(self.part_pts, self.output_width, self.n_parts)

    def ospec(self):
        return IntermediateData(self.part_pts, self.output_width, self.n_parts)

    def elaborate(self, platform):
        m = Module()

        out_part_ops = self.i.part_ops
        out_part_pts = self.i.part_pts

        # create _output_64
        m.submodules.io64 = io64 = IntermediateOut(64, 128, 1)
        m.d.comb += io64.intermed.eq(self.i.output)
        for i in range(8):
            m.d.comb += io64.part_ops[i].eq(out_part_ops[i])
        m.d.comb += self.o.outputs[3].eq(io64.output)

        # create _output_32
        m.submodules.io32 = io32 = IntermediateOut(32, 128, 2)
        m.d.comb += io32.intermed.eq(self.i.output)
        for i in range(8):
            m.d.comb += io32.part_ops[i].eq(out_part_ops[i])
        m.d.comb += self.o.outputs[2].eq(io32.output)

        # create _output_16
        m.submodules.io16 = io16 = IntermediateOut(16, 128, 4)
        m.d.comb += io16.intermed.eq(self.i.output)
        for i in range(8):
            m.d.comb += io16.part_ops[i].eq(out_part_ops[i])
        m.d.comb += self.o.outputs[1].eq(io16.output)

        # create _output_8
        m.submodules.io8 = io8 = IntermediateOut(8, 128, 8)
        m.d.comb += io8.intermed.eq(self.i.output)
        for i in range(8):
            m.d.comb += io8.part_ops[i].eq(out_part_ops[i])
        m.d.comb += self.o.outputs[0].eq(io8.output)

        for i in range(8):
            m.d.comb += self.o.part_ops[i].eq(out_part_ops[i])
        m.d.comb += self.o.part_pts.eq(out_part_pts)
        m.d.comb += self.o.intermediate_output.eq(self.i.output)

        return m


class Mul8_16_32_64(Elaboratable):
    """Signed/Unsigned 8/16/32/64-bit partitioned integer multiplier.

    XXX NOTE: this class is intended for unit test purposes ONLY.

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

        self.id_wid = 0 # num_bits(num_rows)
        self.op_wid = 0
        self.pspec = PipelineSpec(64, self.id_wid, self.op_wid, n_ops=3)
        self.pspec.n_parts = 8

        # parameter(s)
        self.register_levels = list(register_levels)

        self.i = self.ispec()
        self.o = self.ospec()

        # inputs
        self.part_pts = self.i.part_pts
        self.part_ops = self.i.part_ops
        self.a = self.i.a
        self.b = self.i.b

        # output
        self.intermediate_output = self.o.intermediate_output
        self.output = self.o.output

    def ispec(self):
        return InputData()

    def ospec(self):
        return OutputData()

    def elaborate(self, platform):
        m = Module()

        part_pts = self.part_pts

        n_inputs = 64 + 4
        t = AllTerms(self.pspec, n_inputs)
        t.setup(m, self.i)

        terms = t.o.terms

        at = AddReduceInternal(self.pspec, n_inputs, part_pts, partition_step=2)

        i = t.o
        for idx in range(len(at.levels)):
            mcur = at.levels[idx]
            mcur.setup(m, i)
            o = mcur.ospec()
            if idx in self.register_levels:
                m.d.sync += o.eq(mcur.process(i))
            else:
                m.d.comb += o.eq(mcur.process(i))
            i = o # for next loop

        interm = Intermediates(self.pspec, part_pts)
        interm.setup(m, i)
        o = interm.process(interm.i)

        # final output
        finalout = FinalOut(self.pspec, part_pts)
        finalout.setup(m, o)
        m.d.comb += self.o.eq(finalout.process(o))

        return m


if __name__ == "__main__":
    m = Mul8_16_32_64()
    main(m, ports=[m.a,
                   m.b,
                   m.intermediate_output,
                   m.output,
                   *m.part_ops,
                   *m.part_pts.values()])

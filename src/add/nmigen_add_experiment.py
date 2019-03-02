# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat
from nmigen.cli import main, verilog

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase, FPNumBase


class FPState(FPBase):
    def __init__(self, state_from):
        self.state_from = state_from

    def set_inputs(self, inputs):
        self.inputs = inputs
        for k,v in inputs.items():
            setattr(self, k, v)

    def set_outputs(self, outputs):
        self.outputs = outputs
        for k,v in outputs.items():
            setattr(self, k, v)


class FPGetOpMod:
    def __init__(self, width):
        self.in_op = FPOp(width)
        self.out_op = FPNumIn(self.in_op, width)
        self.out_decode = Signal(reset_less=True)

    def setup(self, m, in_op, out_op, out_decode):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_op.copy(in_op)
        m.d.comb += out_op.v.eq(self.out_op.v)
        m.d.comb += out_decode.eq(self.out_decode)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.out_decode.eq((self.in_op.ack) & (self.in_op.stb))
        #m.submodules.get_op_in = self.in_op
        m.submodules.get_op_out = self.out_op
        with m.If(self.out_decode):
            m.d.comb += [
                self.out_op.decode(self.in_op.v),
            ]
        return m


class FPGetOp(FPState):
    """ gets operand
    """

    def __init__(self, in_state, out_state, in_op, width):
        FPState.__init__(self, in_state)
        self.out_state = out_state
        self.mod = FPGetOpMod(width)
        self.in_op = in_op
        self.out_op = FPNumIn(in_op, width)
        self.out_decode = Signal(reset_less=True)

    def action(self, m):
        with m.If(self.out_decode):
            m.next = self.out_state
            m.d.sync += [
                self.in_op.ack.eq(0),
                self.out_op.copy(self.mod.out_op)
            ]
        with m.Else():
            m.d.sync += self.in_op.ack.eq(1)


class FPGetOpB(FPState):
    """ gets operand b
    """

    def __init__(self, in_b, width):
        FPState.__init__(self, "get_b")
        self.in_b = in_b
        self.b = FPNumIn(self.in_b, width)

    def action(self, m):
        self.get_op(m, self.in_b, self.b, "special_cases")


class FPAddSpecialCasesMod:
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width):
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.out_z = FPNumOut(width, False)
        self.out_do_z = Signal(reset_less=True)

    def setup(self, m, in_a, in_b, out_z, out_do_z):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_a.copy(in_a)
        m.d.comb += self.in_b.copy(in_b)
        m.d.comb += out_z.v.eq(self.out_z.v)
        m.d.comb += out_do_z.eq(self.out_do_z)

    def elaborate(self, platform):
        m = Module()

        m.submodules.sc_in_a = self.in_a
        m.submodules.sc_in_b = self.in_b
        m.submodules.sc_out_z = self.out_z

        s_nomatch = Signal()
        m.d.comb += s_nomatch.eq(self.in_a.s != self.in_b.s)

        m_match = Signal()
        m.d.comb += m_match.eq(self.in_a.m == self.in_b.m)

        # if a is NaN or b is NaN return NaN
        with m.If(self.in_a.is_nan | self.in_b.is_nan):
            m.d.comb += self.out_do_z.eq(1)
            m.d.comb += self.out_z.nan(0)

        # XXX WEIRDNESS for FP16 non-canonical NaN handling
        # under review

        ## if a is zero and b is NaN return -b
        #with m.If(a.is_zero & (a.s==0) & b.is_nan):
        #    m.d.comb += self.out_do_z.eq(1)
        #    m.d.comb += z.create(b.s, b.e, Cat(b.m[3:-2], ~b.m[0]))

        ## if b is zero and a is NaN return -a
        #with m.Elif(b.is_zero & (b.s==0) & a.is_nan):
        #    m.d.comb += self.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s, a.e, Cat(a.m[3:-2], ~a.m[0]))

        ## if a is -zero and b is NaN return -b
        #with m.Elif(a.is_zero & (a.s==1) & b.is_nan):
        #    m.d.comb += self.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s & b.s, b.e, Cat(b.m[3:-2], 1))

        ## if b is -zero and a is NaN return -a
        #with m.Elif(b.is_zero & (b.s==1) & a.is_nan):
        #    m.d.comb += self.out_do_z.eq(1)
        #    m.d.comb += z.create(a.s & b.s, a.e, Cat(a.m[3:-2], 1))

        # if a is inf return inf (or NaN)
        with m.Elif(self.in_a.is_inf):
            m.d.comb += self.out_do_z.eq(1)
            m.d.comb += self.out_z.inf(self.in_a.s)
            # if a is inf and signs don't match return NaN
            with m.If(self.in_b.exp_128 & s_nomatch):
                m.d.comb += self.out_z.nan(0)

        # if b is inf return inf
        with m.Elif(self.in_b.is_inf):
            m.d.comb += self.out_do_z.eq(1)
            m.d.comb += self.out_z.inf(self.in_b.s)

        # if a is zero and b zero return signed-a/b
        with m.Elif(self.in_a.is_zero & self.in_b.is_zero):
            m.d.comb += self.out_do_z.eq(1)
            m.d.comb += self.out_z.create(self.in_a.s & self.in_b.s,
                                          self.in_b.e,
                                          self.in_b.m[3:-1])

        # if a is zero return b
        with m.Elif(self.in_a.is_zero):
            m.d.comb += self.out_do_z.eq(1)
            m.d.comb += self.out_z.create(self.in_b.s, self.in_b.e,
                                      self.in_b.m[3:-1])

        # if b is zero return a
        with m.Elif(self.in_b.is_zero):
            m.d.comb += self.out_do_z.eq(1)
            m.d.comb += self.out_z.create(self.in_a.s, self.in_a.e,
                                      self.in_a.m[3:-1])

        # if a equal to -b return zero (+ve zero)
        with m.Elif(s_nomatch & m_match & (self.in_a.e == self.in_b.e)):
            m.d.comb += self.out_do_z.eq(1)
            m.d.comb += self.out_z.zero(0)

        # Denormalised Number checks
        with m.Else():
            m.d.comb += self.out_do_z.eq(0)

        return m


class FPAddSpecialCases(FPState):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width):
        FPState.__init__(self, "special_cases")
        self.mod = FPAddSpecialCasesMod(width)
        self.out_z = FPNumOut(width, False)
        self.out_do_z = Signal(reset_less=True)

    def action(self, m):
        with m.If(self.out_do_z):
            m.d.sync += self.z.v.eq(self.out_z.v) # only take the output
            m.next = "put_z"
        with m.Else():
            m.next = "denormalise"


class FPAddDeNormMod(FPState):

    def __init__(self, width):
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.out_a = FPNumBase(width)
        self.out_b = FPNumBase(width)

    def setup(self, m, in_a, in_b, out_a, out_b):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_a.copy(in_a)
        m.d.comb += self.in_b.copy(in_b)
        m.d.comb += out_a.copy(self.out_a)
        m.d.comb += out_b.copy(self.out_b)

    def elaborate(self, platform):
        m = Module()
        m.submodules.denorm_in_a = self.in_a
        m.submodules.denorm_in_b = self.in_b
        m.submodules.denorm_out_a = self.out_a
        m.submodules.denorm_out_b = self.out_b
        # hmmm, don't like repeating identical code
        m.d.comb += self.out_a.copy(self.in_a)
        with m.If(self.in_a.exp_n127):
            m.d.comb += self.out_a.e.eq(self.in_a.N126) # limit a exponent
        with m.Else():
            m.d.comb += self.out_a.m[-1].eq(1) # set top mantissa bit

        m.d.comb += self.out_b.copy(self.in_b)
        with m.If(self.in_b.exp_n127):
            m.d.comb += self.out_b.e.eq(self.in_b.N126) # limit a exponent
        with m.Else():
            m.d.comb += self.out_b.m[-1].eq(1) # set top mantissa bit

        return m


class FPAddDeNorm(FPState):

    def __init__(self, width):
        FPState.__init__(self, "denormalise")
        self.mod = FPAddDeNormMod(width)
        self.out_a = FPNumBase(width)
        self.out_b = FPNumBase(width)

    def action(self, m):
        # Denormalised Number checks
        m.next = "align"
        m.d.sync += self.a.copy(self.out_a)
        m.d.sync += self.b.copy(self.out_b)


class FPAddAlignMultiMod(FPState):

    def __init__(self, width):
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)
        self.exp_eq = Signal(reset_less=True)

    def setup(self, m, in_a, in_b, out_a, out_b, exp_eq):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_a.copy(in_a)
        m.d.comb += self.in_b.copy(in_b)
        m.d.comb += out_a.copy(self.out_a)
        m.d.comb += out_b.copy(self.out_b)
        m.d.comb += exp_eq.eq(self.exp_eq)

    def elaborate(self, platform):
        # This one however (single-cycle) will do the shift
        # in one go.

        m = Module()

        #m.submodules.align_in_a = self.in_a
        #m.submodules.align_in_b = self.in_b
        m.submodules.align_out_a = self.out_a
        m.submodules.align_out_b = self.out_b

        # NOTE: this does *not* do single-cycle multi-shifting,
        #       it *STAYS* in the align state until exponents match

        # exponent of a greater than b: shift b down
        m.d.comb += self.exp_eq.eq(0)
        m.d.comb += self.out_a.copy(self.in_a)
        m.d.comb += self.out_b.copy(self.in_b)
        agtb = Signal(reset_less=True)
        altb = Signal(reset_less=True)
        m.d.comb += agtb.eq(self.in_a.e > self.in_b.e)
        m.d.comb += altb.eq(self.in_a.e < self.in_b.e)
        with m.If(agtb):
            m.d.comb += self.out_b.shift_down(self.in_b)
        # exponent of b greater than a: shift a down
        with m.Elif(altb):
            m.d.comb += self.out_a.shift_down(self.in_a)
        # exponents equal: move to next stage.
        with m.Else():
            m.d.comb += self.exp_eq.eq(1)
        return m


class FPAddAlignMulti(FPState):

    def __init__(self, width):
        FPState.__init__(self, "align")
        self.mod = FPAddAlignMultiMod(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)
        self.exp_eq = Signal(reset_less=True)

    def action(self, m):
        m.d.sync += self.a.copy(self.out_a)
        m.d.sync += self.b.copy(self.out_b)
        with m.If(self.exp_eq):
            m.next = "add_0"


class FPAddAlignSingleMod:

    def __init__(self, width):
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)
        #self.out_a = FPNumBase(width)
        #self.out_b = FPNumBase(width)

    def setup(self, m, in_a, in_b, out_a, out_b):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_a.copy(in_a)
        m.d.comb += self.in_b.copy(in_b)
        m.d.comb += out_a.copy(self.out_a)
        m.d.comb += out_b.copy(self.out_b)

    def elaborate(self, platform):
        # This one however (single-cycle) will do the shift
        # in one go.

        m = Module()

        #m.submodules.align_in_a = self.in_a
        #m.submodules.align_in_b = self.in_b
        m.submodules.align_out_a = self.out_a
        m.submodules.align_out_b = self.out_b

        # XXX TODO: the shifter used here is quite expensive
        # having only one would be better

        ediff = Signal((len(self.in_a.e), True), reset_less=True)
        ediffr = Signal((len(self.in_a.e), True), reset_less=True)
        m.d.comb += ediff.eq(self.in_a.e - self.in_b.e)
        m.d.comb += ediffr.eq(self.in_b.e - self.in_a.e)
        m.d.comb += self.out_a.copy(self.in_a)
        m.d.comb += self.out_b.copy(self.in_b)
        with m.If(ediff > 0):
            m.d.comb += self.out_b.shift_down_multi(ediff)
        # exponent of b greater than a: shift a down
        with m.Elif(ediff < 0):
            m.d.comb += self.out_a.shift_down_multi(ediffr)
        return m


class FPAddAlignSingle(FPState):

    def __init__(self, width):
        FPState.__init__(self, "align")
        self.mod = FPAddAlignSingleMod(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)

    def action(self, m):
        m.d.sync += self.a.copy(self.out_a)
        m.d.sync += self.b.copy(self.out_b)
        m.next = "add_0"


class FPAddStage0Mod:

    def __init__(self, width):
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.in_z = FPNumBase(width, False)
        self.out_z = FPNumBase(width, False)
        self.out_tot = Signal(self.out_z.m_width + 4, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.submodules.add0_in_a = self.in_a
        m.submodules.add0_in_b = self.in_b
        m.submodules.add0_out_z = self.out_z

        m.d.comb += self.out_z.e.eq(self.in_a.e)

        # store intermediate tests (and zero-extended mantissas)
        seq = Signal(reset_less=True)
        mge = Signal(reset_less=True)
        am0 = Signal(len(self.in_a.m)+1, reset_less=True)
        bm0 = Signal(len(self.in_b.m)+1, reset_less=True)
        m.d.comb += [seq.eq(self.in_a.s == self.in_b.s),
                     mge.eq(self.in_a.m >= self.in_b.m),
                     am0.eq(Cat(self.in_a.m, 0)),
                     bm0.eq(Cat(self.in_b.m, 0))
                    ]
        # same-sign (both negative or both positive) add mantissas
        with m.If(seq):
            m.d.comb += [
                self.out_tot.eq(am0 + bm0),
                self.out_z.s.eq(self.in_a.s)
            ]
        # a mantissa greater than b, use a
        with m.Elif(mge):
            m.d.comb += [
                self.out_tot.eq(am0 - bm0),
                self.out_z.s.eq(self.in_a.s)
            ]
        # b mantissa greater than a, use b
        with m.Else():
            m.d.comb += [
                self.out_tot.eq(bm0 - am0),
                self.out_z.s.eq(self.in_b.s)
        ]
        return m


class FPAddStage0(FPState):
    """ First stage of add.  covers same-sign (add) and subtract
        special-casing when mantissas are greater or equal, to
        give greatest accuracy.
    """

    def __init__(self, width):
        FPState.__init__(self, "add_0")
        self.mod = FPAddStage0Mod(width)
        self.out_z = FPNumBase(width, False)
        self.out_tot = Signal(self.out_z.m_width + 4, reset_less=True)

    def setup(self, m, in_a, in_b):
        """ links module to inputs and outputs
        """
        m.submodules.add0 = self.mod

        m.d.comb += self.mod.in_a.copy(in_a)
        m.d.comb += self.mod.in_b.copy(in_b)

    def action(self, m):
        m.next = "add_1"
        # NOTE: these could be done as combinatorial (merge add0+add1)
        m.d.sync += self.out_z.copy(self.mod.out_z)
        m.d.sync += self.out_tot.eq(self.mod.out_tot)


class FPAddStage1Mod(FPState):
    """ Second stage of add: preparation for normalisation.
        detects when tot sum is too big (tot[27] is kinda a carry bit)
    """

    def __init__(self, width):
        self.out_norm = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.in_tot = Signal(self.in_z.m_width + 4, reset_less=True)
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()

    def elaborate(self, platform):
        m = Module()
        #m.submodules.norm1_in_overflow = self.in_of
        #m.submodules.norm1_out_overflow = self.out_of
        #m.submodules.norm1_in_z = self.in_z
        #m.submodules.norm1_out_z = self.out_z
        m.d.comb += self.out_z.copy(self.in_z)
        # tot[27] gets set when the sum overflows. shift result down
        with m.If(self.in_tot[-1]):
            m.d.comb += [
                self.out_z.m.eq(self.in_tot[4:]),
                self.out_of.m0.eq(self.in_tot[4]),
                self.out_of.guard.eq(self.in_tot[3]),
                self.out_of.round_bit.eq(self.in_tot[2]),
                self.out_of.sticky.eq(self.in_tot[1] | self.in_tot[0]),
                self.out_z.e.eq(self.in_z.e + 1)
        ]
        # tot[27] zero case
        with m.Else():
            m.d.comb += [
                self.out_z.m.eq(self.in_tot[3:]),
                self.out_of.m0.eq(self.in_tot[3]),
                self.out_of.guard.eq(self.in_tot[2]),
                self.out_of.round_bit.eq(self.in_tot[1]),
                self.out_of.sticky.eq(self.in_tot[0])
        ]
        return m


class FPAddStage1(FPState):

    def __init__(self, width):
        FPState.__init__(self, "add_1")
        self.mod = FPAddStage1Mod(width)
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()
        self.norm_stb = Signal()

    def setup(self, m, in_tot, in_z):
        """ links module to inputs and outputs
        """
        m.submodules.add1 = self.mod

        m.d.comb += self.mod.in_z.copy(in_z)
        m.d.comb += self.mod.in_tot.eq(in_tot)

        m.d.sync += self.norm_stb.eq(0) # sets to zero when not in add1 state

    def action(self, m):
        m.submodules.add1_out_overflow = self.out_of
        m.d.sync += self.out_of.copy(self.mod.out_of)
        m.d.sync += self.out_z.copy(self.mod.out_z)
        m.d.sync += self.norm_stb.eq(1)
        m.next = "normalise_1"


class FPNorm1Mod:

    def __init__(self, width):
        self.width = width
        self.in_select = Signal(reset_less=True)
        self.out_norm = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.in_of = Overflow()
        self.temp_z = FPNumBase(width, False)
        self.temp_of = Overflow()
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()

    def elaborate(self, platform):
        m = Module()
        m.submodules.norm1_out_z = self.out_z
        m.submodules.norm1_out_overflow = self.out_of
        m.submodules.norm1_temp_z = self.temp_z
        m.submodules.norm1_temp_of = self.temp_of
        m.submodules.norm1_in_z = self.in_z
        m.submodules.norm1_in_overflow = self.in_of
        in_z = FPNumBase(self.width, False)
        in_of = Overflow()
        m.submodules.norm1_insel_z = in_z
        m.submodules.norm1_insel_overflow = in_of
        # select which of temp or in z/of to use
        with m.If(self.in_select):
            m.d.comb += in_z.copy(self.in_z)
            m.d.comb += in_of.copy(self.in_of)
        with m.Else():
            m.d.comb += in_z.copy(self.temp_z)
            m.d.comb += in_of.copy(self.temp_of)
        # initialise out from in (overridden below)
        m.d.comb += self.out_z.copy(in_z)
        m.d.comb += self.out_of.copy(in_of)
        # normalisation increase/decrease conditions
        decrease = Signal(reset_less=True)
        increase = Signal(reset_less=True)
        m.d.comb += decrease.eq(in_z.m_msbzero & in_z.exp_gt_n126)
        m.d.comb += increase.eq(in_z.exp_lt_n126)
        m.d.comb += self.out_norm.eq(decrease | increase) # loop-end condition
        # decrease exponent
        with m.If(decrease):
            m.d.comb += [
                self.out_z.e.eq(in_z.e - 1),  # DECREASE exponent
                self.out_z.m.eq(in_z.m << 1), # shift mantissa UP
                self.out_z.m[0].eq(in_of.guard), # steal guard (was tot[2])
                self.out_of.guard.eq(in_of.round_bit), # round (was tot[1])
                self.out_of.round_bit.eq(0),        # reset round bit
                self.out_of.m0.eq(in_of.guard),
            ]
        # increase exponent
        with m.If(increase):
            m.d.comb += [
                self.out_z.e.eq(in_z.e + 1),  # INCREASE exponent
                self.out_z.m.eq(in_z.m >> 1), # shift mantissa DOWN
                self.out_of.guard.eq(in_z.m[0]),
                self.out_of.m0.eq(in_z.m[1]),
                self.out_of.round_bit.eq(in_of.guard),
                self.out_of.sticky.eq(in_of.sticky | in_of.round_bit)
            ]

        return m


class FPNorm1(FPState):

    def __init__(self, width):
        FPState.__init__(self, "normalise_1")
        self.mod = FPNorm1Mod(width)
        self.stb = Signal(reset_less=True)
        self.ack = Signal(reset=0, reset_less=True)
        self.out_norm = Signal(reset_less=True)
        self.in_accept = Signal(reset_less=True)
        self.temp_z = FPNumBase(width)
        self.temp_of = Overflow()
        self.out_z = FPNumBase(width)
        self.out_of = Overflow()

    def setup(self, m, in_z, in_of, norm_stb):
        """ links module to inputs and outputs
        """
        m.submodules.normalise_1 = self.mod

        m.d.comb += self.mod.in_z.copy(in_z)
        m.d.comb += self.mod.in_of.copy(in_of)

        m.d.comb += self.mod.in_select.eq(self.in_accept)
        m.d.comb += self.mod.temp_z.copy(self.temp_z)
        m.d.comb += self.mod.temp_of.copy(self.temp_of)

        m.d.comb += self.out_z.copy(self.mod.out_z)
        m.d.comb += self.out_of.copy(self.mod.out_of)
        m.d.comb += self.out_norm.eq(self.mod.out_norm)

        m.d.comb += self.stb.eq(norm_stb)
        m.d.sync += self.ack.eq(0) # sets to zero when not in normalise_1 state

    def action(self, m):
        m.d.comb += self.in_accept.eq((~self.ack) & (self.stb))
        m.d.sync += self.of.copy(self.out_of)
        m.d.sync += self.z.copy(self.out_z)
        m.d.sync += self.temp_of.copy(self.out_of)
        m.d.sync += self.temp_z.copy(self.out_z)
        with m.If(self.out_norm):
            with m.If(self.in_accept):
                m.d.sync += [
                    self.ack.eq(1),
                ]
            with m.Else():
                m.d.sync += self.ack.eq(0)
        with m.Else():
            # normalisation not required (or done).
            m.next = "round"
            m.d.sync += self.ack.eq(1)


class FPRoundMod:

    def __init__(self, width):
        self.in_roundz = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.out_z = FPNumBase(width, False)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.out_z.copy(self.in_z)
        with m.If(self.in_roundz):
            m.d.comb += self.out_z.m.eq(self.in_z.m + 1) # mantissa rounds up
            with m.If(self.in_z.m == self.in_z.m1s): # all 1s
                m.d.comb += self.out_z.e.eq(self.in_z.e + 1) # exponent up
        return m


class FPRound(FPState):

    def __init__(self, width):
        FPState.__init__(self, "round")
        self.mod = FPRoundMod(width)
        self.out_z = FPNumBase(width)

    def setup(self, m, in_z, in_of):
        """ links module to inputs and outputs
        """
        m.submodules.roundz = self.mod

        m.d.comb += self.mod.in_z.copy(in_z)
        m.d.comb += self.out_z.copy(self.mod.out_z)
        m.d.comb += self.mod.in_roundz.eq(in_of.roundz)

    def action(self, m):
        m.d.sync += self.z.copy(self.out_z)
        m.next = "corrections"


class FPCorrectionsMod:

    def __init__(self, width):
        self.in_z = FPNumOut(width, False)
        self.out_z = FPNumOut(width, False)

    def setup(self, m, in_z, out_z):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_z.copy(in_z)
        m.d.comb += out_z.copy(self.out_z)

    def elaborate(self, platform):
        m = Module()
        m.submodules.corr_in_z = self.in_z
        m.submodules.corr_out_z = self.out_z
        m.d.comb += self.out_z.copy(self.in_z)
        with m.If(self.in_z.is_denormalised):
            m.d.comb += self.out_z.e.eq(self.in_z.N127)

        #        with m.If(self.in_z.is_overflowed):
        #            m.d.comb += self.out_z.inf(self.in_z.s)
        #        with m.Else():
        #            m.d.comb += self.out_z.create(self.in_z.s, self.in_z.e, self.in_z.m)
        return m


class FPCorrections(FPState):

    def __init__(self, width):
        FPState.__init__(self, "corrections")
        self.mod = FPCorrectionsMod(width)
        self.out_z = FPNumBase(width)

    def action(self, m):
        m.d.sync += self.z.copy(self.out_z)
        m.next = "pack"


class FPPackMod:

    def __init__(self, width):
        self.in_z = FPNumOut(width, False)
        self.out_z = FPNumOut(width, False)

    def setup(self, m, in_z, out_z):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_z.copy(in_z)
        m.d.comb += out_z.v.eq(self.out_z.v)

    def elaborate(self, platform):
        m = Module()
        m.submodules.pack_in_z = self.in_z
        with m.If(self.in_z.is_overflowed):
            m.d.comb += self.out_z.inf(self.in_z.s)
        with m.Else():
            m.d.comb += self.out_z.create(self.in_z.s, self.in_z.e, self.in_z.m)
        return m


class FPPack(FPState):

    def __init__(self, width):
        FPState.__init__(self, "pack")
        self.mod = FPPackMod(width)
        self.out_z = FPNumOut(width, False)

    def action(self, m):
        m.d.sync += self.z.v.eq(self.out_z.v)
        m.next = "pack_put_z"


class FPPutZ(FPState):

    def action(self, m):
        self.put_z(m, self.z, self.out_z, "get_a")


class FPADD:

    def __init__(self, width, single_cycle=False):
        self.width = width
        self.single_cycle = single_cycle

        self.in_a  = FPOp(width)
        self.in_b  = FPOp(width)
        self.out_z = FPOp(width)

        self.states = []

    def add_state(self, state):
        self.states.append(state)
        return state

    def get_fragment(self, platform=None):
        """ creates the HDL code-fragment for FPAdd
        """
        m = Module()

        # Latches
        z = FPNumOut(self.width, False)
        m.submodules.fpnum_z = z

        w = z.m_width + 4

        geta = self.add_state(FPGetOp("get_a", "get_b",
                                      self.in_a, self.width))
        a = geta.out_op
        geta.mod.setup(m, self.in_a, geta.out_op, geta.out_decode)
        m.submodules.get_a = geta.mod

        getb = self.add_state(FPGetOp("get_b", "special_cases",
                                      self.in_b, self.width))
        b = getb.out_op
        getb.mod.setup(m, self.in_b, getb.out_op, getb.out_decode)
        m.submodules.get_b = getb.mod

        sc = self.add_state(FPAddSpecialCases(self.width))
        sc.set_inputs({"a": a, "b": b})
        sc.set_outputs({"z": z})
        sc.mod.setup(m, a, b, sc.out_z, sc.out_do_z)
        m.submodules.specialcases = sc.mod

        dn = self.add_state(FPAddDeNorm(self.width))
        dn.set_inputs({"a": a, "b": b})
        #dn.set_outputs({"a": a, "b": b}) # XXX outputs same as inputs
        dn.mod.setup(m, a, b, dn.out_a, dn.out_b)
        m.submodules.denormalise = dn.mod

        if self.single_cycle:
            alm = self.add_state(FPAddAlignSingle(self.width))
            alm.set_inputs({"a": a, "b": b})
            alm.set_outputs({"a": a, "b": b}) # XXX outputs same as inputs
            alm.mod.setup(m, a, b, alm.out_a, alm.out_b)
        else:
            alm = self.add_state(FPAddAlignMulti(self.width))
            alm.set_inputs({"a": a, "b": b})
            #alm.set_outputs({"a": a, "b": b}) # XXX outputs same as inputs
            alm.mod.setup(m, a, b, alm.out_a, alm.out_b, alm.exp_eq)
        m.submodules.align = alm.mod

        add0 = self.add_state(FPAddStage0(self.width))
        add0.setup(m, alm.out_a, alm.out_b)

        add1 = self.add_state(FPAddStage1(self.width))
        add1.setup(m, add0.out_tot, add0.out_z)

        az = add1.out_z

        n1 = self.add_state(FPNorm1(self.width))
        n1.set_inputs({"z": az, "of": add1.out_of})  # XXX Z as output
        n1.set_outputs({"z": az})  # XXX Z as output
        n1.setup(m, az, add1.out_of, add1.norm_stb)

        rnz = FPNumOut(self.width, False)
        m.submodules.fpnum_rnz = rnz

        rn = self.add_state(FPRound(self.width))
        rn.set_inputs({"of": n1.out_of})
        rn.set_outputs({"z": rnz})
        rn.setup(m, n1.out_z, add1.out_of)

        cor = self.add_state(FPCorrections(self.width))
        cor.set_inputs({"z": rnz})  # XXX Z as output
        cor.mod.setup(m, rnz, cor.out_z)
        m.submodules.corrections = cor.mod

        pa = self.add_state(FPPack(self.width))
        pa.set_inputs({"z": cor.out_z})  # XXX Z as output
        pa.mod.setup(m, cor.out_z, pa.out_z)
        m.submodules.pack = pa.mod

        ppz = self.add_state(FPPutZ("pack_put_z"))
        ppz.set_inputs({"z": pa.out_z})
        ppz.set_outputs({"out_z": self.out_z})

        pz = self.add_state(FPPutZ("put_z"))
        pz.set_inputs({"z": z})
        pz.set_outputs({"out_z": self.out_z})

        with m.FSM() as fsm:

            for state in self.states:
                with m.State(state.state_from):
                    state.action(m)

        return m


if __name__ == "__main__":
    alu = FPADD(width=32)
    main(alu, ports=alu.in_a.ports() + alu.in_b.ports() + alu.out_z.ports())


    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                        ports=alu.in_a.ports() + \
    #                              alu.in_b.ports() + \
    #                              alu.out_z.ports())

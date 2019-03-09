# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Mux
from nmigen.lib.coding import PriorityEncoder
from nmigen.cli import main, verilog

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase, FPNumBase
from fpbase import MultiShiftRMerge, Trigger
#from fpbase import FPNumShiftMultiRight

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
        self.out_op = Signal(width)
        self.out_decode = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.out_decode.eq((self.in_op.ack) & (self.in_op.stb))
        m.submodules.get_op_in = self.in_op
        #m.submodules.get_op_out = self.out_op
        with m.If(self.out_decode):
            m.d.comb += [
                self.out_op.eq(self.in_op.v),
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
        self.out_op = Signal(width)
        self.out_decode = Signal(reset_less=True)

    def setup(self, m, in_op):
        """ links module to inputs and outputs
        """
        setattr(m.submodules, self.state_from, self.mod)
        m.d.comb += self.mod.in_op.copy(in_op)
        #m.d.comb += self.out_op.eq(self.mod.out_op)
        m.d.comb += self.out_decode.eq(self.mod.out_decode)

    def action(self, m):
        with m.If(self.out_decode):
            m.next = self.out_state
            m.d.sync += [
                self.in_op.ack.eq(0),
                self.out_op.eq(self.mod.out_op)
            ]
        with m.Else():
            m.d.sync += self.in_op.ack.eq(1)


class FPGet2OpMod(Trigger):
    def __init__(self, width):
        Trigger.__init__(self)
        self.in_op1 = Signal(width, reset_less=True)
        self.in_op2 = Signal(width, reset_less=True)
        self.out_op1 = FPNumIn(None, width)
        self.out_op2 = FPNumIn(None, width)

    def elaborate(self, platform):
        m = Trigger.elaborate(self, platform)
        #m.submodules.get_op_in = self.in_op
        m.submodules.get_op1_out = self.out_op1
        m.submodules.get_op2_out = self.out_op2
        with m.If(self.trigger):
            m.d.comb += [
                self.out_op1.decode(self.in_op1),
                self.out_op2.decode(self.in_op2),
            ]
        return m


class FPGet2Op(FPState):
    """ gets operands
    """

    def __init__(self, in_state, out_state, in_op1, in_op2, width):
        FPState.__init__(self, in_state)
        self.out_state = out_state
        self.mod = FPGet2OpMod(width)
        self.in_op1 = in_op1
        self.in_op2 = in_op2
        self.out_op1 = FPNumIn(None, width)
        self.out_op2 = FPNumIn(None, width)
        self.in_stb = Signal(reset_less=True)
        self.out_ack = Signal(reset_less=True)
        self.out_decode = Signal(reset_less=True)

    def setup(self, m, in_op1, in_op2, in_stb, in_ack):
        """ links module to inputs and outputs
        """
        m.submodules.get_ops = self.mod
        m.d.comb += self.mod.in_op1.eq(in_op1)
        m.d.comb += self.mod.in_op2.eq(in_op2)
        m.d.comb += self.mod.stb.eq(in_stb)
        m.d.comb += self.out_ack.eq(self.mod.ack)
        m.d.comb += self.out_decode.eq(self.mod.trigger)
        m.d.comb += in_ack.eq(self.mod.ack)

    def action(self, m):
        with m.If(self.out_decode):
            m.next = self.out_state
            m.d.sync += [
                self.mod.ack.eq(0),
                #self.out_op1.v.eq(self.mod.out_op1.v),
                #self.out_op2.v.eq(self.mod.out_op2.v),
                self.out_op1.copy(self.mod.out_op1),
                self.out_op2.copy(self.mod.out_op2)
            ]
        with m.Else():
            m.d.sync += self.mod.ack.eq(1)


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

    def setup(self, m, in_a, in_b, out_do_z):
        """ links module to inputs and outputs
        """
        m.submodules.specialcases = self
        m.d.comb += self.in_a.copy(in_a)
        m.d.comb += self.in_b.copy(in_b)
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


class FPID:
    def __init__(self, id_wid):
        self.id_wid = id_wid
        if self.id_wid:
            self.in_mid = Signal(id_wid, reset_less=True)
            self.out_mid = Signal(id_wid, reset_less=True)
        else:
            self.in_mid = None
            self.out_mid = None

    def idsync(self, m):
        if self.id_wid is not None:
            m.d.sync += self.out_mid.eq(self.in_mid)


class FPAddSpecialCases(FPState, FPID):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "special_cases")
        FPID.__init__(self, id_wid)
        self.mod = FPAddSpecialCasesMod(width)
        self.out_z = FPNumOut(width, False)
        self.out_do_z = Signal(reset_less=True)

    def setup(self, m, in_a, in_b, in_mid):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_a, in_b, self.out_do_z)
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        with m.If(self.out_do_z):
            m.d.sync += self.out_z.v.eq(self.mod.out_z.v) # only take the output
            m.next = "put_z"
        with m.Else():
            m.next = "denormalise"


class FPAddSpecialCasesDeNorm(FPState, FPID):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "special_cases")
        FPID.__init__(self, id_wid)
        self.smod = FPAddSpecialCasesMod(width)
        self.out_z = FPNumOut(width, False)
        self.out_do_z = Signal(reset_less=True)

        self.dmod = FPAddDeNormMod(width)
        self.out_a = FPNumBase(width)
        self.out_b = FPNumBase(width)

    def setup(self, m, in_a, in_b, in_mid):
        """ links module to inputs and outputs
        """
        self.smod.setup(m, in_a, in_b, self.out_do_z)
        self.dmod.setup(m, in_a, in_b)
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        with m.If(self.out_do_z):
            m.d.sync += self.out_z.v.eq(self.smod.out_z.v) # only take output
            m.next = "put_z"
        with m.Else():
            m.next = "align"
            m.d.sync += self.out_a.copy(self.dmod.out_a)
            m.d.sync += self.out_b.copy(self.dmod.out_b)


class FPAddDeNormMod(FPState):

    def __init__(self, width):
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.out_a = FPNumBase(width)
        self.out_b = FPNumBase(width)

    def setup(self, m, in_a, in_b):
        """ links module to inputs and outputs
        """
        m.submodules.denormalise = self
        m.d.comb += self.in_a.copy(in_a)
        m.d.comb += self.in_b.copy(in_b)

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


class FPAddDeNorm(FPState, FPID):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "denormalise")
        FPID.__init__(self, id_wid)
        self.mod = FPAddDeNormMod(width)
        self.out_a = FPNumBase(width)
        self.out_b = FPNumBase(width)

    def setup(self, m, in_a, in_b, in_mid):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_a, in_b)
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        # Denormalised Number checks
        m.next = "align"
        m.d.sync += self.out_a.copy(self.mod.out_a)
        m.d.sync += self.out_b.copy(self.mod.out_b)


class FPAddAlignMultiMod(FPState):

    def __init__(self, width):
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)
        self.exp_eq = Signal(reset_less=True)

    def elaborate(self, platform):
        # This one however (single-cycle) will do the shift
        # in one go.

        m = Module()

        m.submodules.align_in_a = self.in_a
        m.submodules.align_in_b = self.in_b
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


class FPAddAlignMulti(FPState, FPID):

    def __init__(self, width, id_wid):
        FPID.__init__(self, id_wid)
        FPState.__init__(self, "align")
        self.mod = FPAddAlignMultiMod(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)
        self.exp_eq = Signal(reset_less=True)

    def setup(self, m, in_a, in_b, in_mid):
        """ links module to inputs and outputs
        """
        m.submodules.align = self.mod
        m.d.comb += self.mod.in_a.copy(in_a)
        m.d.comb += self.mod.in_b.copy(in_b)
        #m.d.comb += self.out_a.copy(self.mod.out_a)
        #m.d.comb += self.out_b.copy(self.mod.out_b)
        m.d.comb += self.exp_eq.eq(self.mod.exp_eq)
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        m.d.sync += self.out_a.copy(self.mod.out_a)
        m.d.sync += self.out_b.copy(self.mod.out_b)
        with m.If(self.exp_eq):
            m.next = "add_0"


class FPAddAlignSingleMod:

    def __init__(self, width):
        self.width = width
        self.in_a = FPNumBase(width)
        self.in_b = FPNumBase(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)

    def elaborate(self, platform):
        """ Aligns A against B or B against A, depending on which has the
            greater exponent.  This is done in a *single* cycle using
            variable-width bit-shift

            the shifter used here is quite expensive in terms of gates.
            Mux A or B in (and out) into temporaries, as only one of them
            needs to be aligned against the other
        """
        m = Module()

        m.submodules.align_in_a = self.in_a
        m.submodules.align_in_b = self.in_b
        m.submodules.align_out_a = self.out_a
        m.submodules.align_out_b = self.out_b

        # temporary (muxed) input and output to be shifted
        t_inp = FPNumBase(self.width)
        t_out = FPNumIn(None, self.width)
        espec = (len(self.in_a.e), True)
        msr = MultiShiftRMerge(self.in_a.m_width, espec)
        m.submodules.align_t_in = t_inp
        m.submodules.align_t_out = t_out
        m.submodules.multishift_r = msr

        ediff = Signal(espec, reset_less=True)
        ediffr = Signal(espec, reset_less=True)
        tdiff = Signal(espec, reset_less=True)
        elz = Signal(reset_less=True)
        egz = Signal(reset_less=True)

        # connect multi-shifter to t_inp/out mantissa (and tdiff)
        m.d.comb += msr.inp.eq(t_inp.m)
        m.d.comb += msr.diff.eq(tdiff)
        m.d.comb += t_out.m.eq(msr.m)
        m.d.comb += t_out.e.eq(t_inp.e + tdiff)
        m.d.comb += t_out.s.eq(t_inp.s)

        m.d.comb += ediff.eq(self.in_a.e - self.in_b.e)
        m.d.comb += ediffr.eq(self.in_b.e - self.in_a.e)
        m.d.comb += elz.eq(self.in_a.e < self.in_b.e)
        m.d.comb += egz.eq(self.in_a.e > self.in_b.e)

        # default: A-exp == B-exp, A and B untouched (fall through)
        m.d.comb += self.out_a.copy(self.in_a)
        m.d.comb += self.out_b.copy(self.in_b)
        # only one shifter (muxed)
        #m.d.comb += t_out.shift_down_multi(tdiff, t_inp)
        # exponent of a greater than b: shift b down
        with m.If(egz):
            m.d.comb += [t_inp.copy(self.in_b),
                         tdiff.eq(ediff),
                         self.out_b.copy(t_out),
                         self.out_b.s.eq(self.in_b.s), # whoops forgot sign
                        ]
        # exponent of b greater than a: shift a down
        with m.Elif(elz):
            m.d.comb += [t_inp.copy(self.in_a),
                         tdiff.eq(ediffr),
                         self.out_a.copy(t_out),
                         self.out_a.s.eq(self.in_a.s), # whoops forgot sign
                        ]
        return m


class FPAddAlignSingle(FPState, FPID):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "align")
        FPID.__init__(self, id_wid)
        self.mod = FPAddAlignSingleMod(width)
        self.out_a = FPNumIn(None, width)
        self.out_b = FPNumIn(None, width)

    def setup(self, m, in_a, in_b, in_mid):
        """ links module to inputs and outputs
        """
        m.submodules.align = self.mod
        m.d.comb += self.mod.in_a.copy(in_a)
        m.d.comb += self.mod.in_b.copy(in_b)
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        # NOTE: could be done as comb
        m.d.sync += self.out_a.copy(self.mod.out_a)
        m.d.sync += self.out_b.copy(self.mod.out_b)
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


class FPAddStage0(FPState, FPID):
    """ First stage of add.  covers same-sign (add) and subtract
        special-casing when mantissas are greater or equal, to
        give greatest accuracy.
    """

    def __init__(self, width, id_wid):
        FPState.__init__(self, "add_0")
        FPID.__init__(self, id_wid)
        self.mod = FPAddStage0Mod(width)
        self.out_z = FPNumBase(width, False)
        self.out_tot = Signal(self.out_z.m_width + 4, reset_less=True)

    def setup(self, m, in_a, in_b, in_mid):
        """ links module to inputs and outputs
        """
        m.submodules.add0 = self.mod
        m.d.comb += self.mod.in_a.copy(in_a)
        m.d.comb += self.mod.in_b.copy(in_b)
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        # NOTE: these could be done as combinatorial (merge add0+add1)
        m.d.sync += self.out_z.copy(self.mod.out_z)
        m.d.sync += self.out_tot.eq(self.mod.out_tot)
        m.next = "add_1"


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


class FPAddStage1(FPState, FPID):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "add_1")
        FPID.__init__(self, id_wid)
        self.mod = FPAddStage1Mod(width)
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()
        self.norm_stb = Signal()

    def setup(self, m, in_tot, in_z, in_mid):
        """ links module to inputs and outputs
        """
        m.submodules.add1 = self.mod
        m.submodules.add1_out_overflow = self.out_of

        m.d.comb += self.mod.in_z.copy(in_z)
        m.d.comb += self.mod.in_tot.eq(in_tot)

        m.d.sync += self.norm_stb.eq(0) # sets to zero when not in add1 state

        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        m.d.sync += self.out_of.copy(self.mod.out_of)
        m.d.sync += self.out_z.copy(self.mod.out_z)
        m.d.sync += self.norm_stb.eq(1)
        m.next = "normalise_1"


class FPNorm1ModSingle:

    def __init__(self, width):
        self.width = width
        self.out_norm = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.in_of = Overflow()
        self.out_z = FPNumBase(width, False)
        self.out_of = Overflow()

    def setup(self, m, in_z, in_of, out_z):
        """ links module to inputs and outputs
        """
        m.submodules.normalise_1 = self

        m.d.comb += self.in_z.copy(in_z)
        m.d.comb += self.in_of.copy(in_of)

        m.d.comb += out_z.copy(self.out_z)

    def elaborate(self, platform):
        m = Module()

        mwid = self.out_z.m_width+2
        pe = PriorityEncoder(mwid)
        m.submodules.norm_pe = pe

        m.submodules.norm1_out_z = self.out_z
        m.submodules.norm1_out_overflow = self.out_of
        m.submodules.norm1_in_z = self.in_z
        m.submodules.norm1_in_overflow = self.in_of

        in_z = FPNumBase(self.width, False)
        in_of = Overflow()
        m.submodules.norm1_insel_z = in_z
        m.submodules.norm1_insel_overflow = in_of

        espec = (len(in_z.e), True)
        ediff_n126 = Signal(espec, reset_less=True)
        msr = MultiShiftRMerge(mwid, espec)
        m.submodules.multishift_r = msr

        m.d.comb += in_z.copy(self.in_z)
        m.d.comb += in_of.copy(self.in_of)
        # initialise out from in (overridden below)
        m.d.comb += self.out_z.copy(in_z)
        m.d.comb += self.out_of.copy(in_of)
        # normalisation increase/decrease conditions
        decrease = Signal(reset_less=True)
        increase = Signal(reset_less=True)
        m.d.comb += decrease.eq(in_z.m_msbzero & in_z.exp_gt_n126)
        m.d.comb += increase.eq(in_z.exp_lt_n126)
        # decrease exponent
        with m.If(decrease):
            # *sigh* not entirely obvious: count leading zeros (clz)
            # with a PriorityEncoder: to find from the MSB
            # we reverse the order of the bits.
            temp_m = Signal(mwid, reset_less=True)
            temp_s = Signal(mwid+1, reset_less=True)
            clz = Signal((len(in_z.e), True), reset_less=True)
            # make sure that the amount to decrease by does NOT
            # go below the minimum non-INF/NaN exponent
            limclz = Mux(in_z.exp_sub_n126 > pe.o, pe.o,
                         in_z.exp_sub_n126)
            m.d.comb += [
                # cat round and guard bits back into the mantissa
                temp_m.eq(Cat(in_of.round_bit, in_of.guard, in_z.m)),
                pe.i.eq(temp_m[::-1]),          # inverted
                clz.eq(limclz),                 # count zeros from MSB down
                temp_s.eq(temp_m << clz),       # shift mantissa UP
                self.out_z.e.eq(in_z.e - clz),  # DECREASE exponent
                self.out_z.m.eq(temp_s[2:]),    # exclude bits 0&1
                self.out_of.m0.eq(temp_s[2]),   # copy of mantissa[0]
                # overflow in bits 0..1: got shifted too (leave sticky)
                self.out_of.guard.eq(temp_s[1]),     # guard
                self.out_of.round_bit.eq(temp_s[0]), # round
            ]
        # increase exponent
        with m.Elif(increase):
            temp_m = Signal(mwid+1, reset_less=True)
            m.d.comb += [
                temp_m.eq(Cat(in_of.sticky, in_of.round_bit, in_of.guard,
                              in_z.m)),
                ediff_n126.eq(in_z.N126 - in_z.e),
                # connect multi-shifter to inp/out mantissa (and ediff)
                msr.inp.eq(temp_m),
                msr.diff.eq(ediff_n126),
                self.out_z.m.eq(msr.m[3:]),
                self.out_of.m0.eq(temp_s[3]),   # copy of mantissa[0]
                # overflow in bits 0..1: got shifted too (leave sticky)
                self.out_of.guard.eq(temp_s[2]),     # guard
                self.out_of.round_bit.eq(temp_s[1]), # round
                self.out_of.sticky.eq(temp_s[0]), # sticky
                self.out_z.e.eq(in_z.e + ediff_n126),
            ]

        return m


class FPNorm1ModMulti:

    def __init__(self, width, single_cycle=True):
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
        m.d.comb += self.out_norm.eq(decrease | increase) # loop-end
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
        with m.Elif(increase):
            m.d.comb += [
                self.out_z.e.eq(in_z.e + 1),  # INCREASE exponent
                self.out_z.m.eq(in_z.m >> 1), # shift mantissa DOWN
                self.out_of.guard.eq(in_z.m[0]),
                self.out_of.m0.eq(in_z.m[1]),
                self.out_of.round_bit.eq(in_of.guard),
                self.out_of.sticky.eq(in_of.sticky | in_of.round_bit)
            ]

        return m


class FPNorm1Single(FPState, FPID):

    def __init__(self, width, id_wid, single_cycle=True):
        FPID.__init__(self, id_wid)
        FPState.__init__(self, "normalise_1")
        self.mod = FPNorm1ModSingle(width)
        self.out_norm = Signal(reset_less=True)
        self.out_z = FPNumBase(width)
        self.out_roundz = Signal(reset_less=True)

    def setup(self, m, in_z, in_of, in_mid):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z, in_of, self.out_z)

        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        m.d.sync += self.out_roundz.eq(self.mod.out_of.roundz)
        m.next = "round"


class FPNorm1Multi(FPState, FPID):

    def __init__(self, width, id_wid):
        FPID.__init__(self, id_wid)
        FPState.__init__(self, "normalise_1")
        self.mod = FPNorm1ModMulti(width)
        self.stb = Signal(reset_less=True)
        self.ack = Signal(reset=0, reset_less=True)
        self.out_norm = Signal(reset_less=True)
        self.in_accept = Signal(reset_less=True)
        self.temp_z = FPNumBase(width)
        self.temp_of = Overflow()
        self.out_z = FPNumBase(width)
        self.out_roundz = Signal(reset_less=True)

    def setup(self, m, in_z, in_of, norm_stb, in_mid):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z, in_of, norm_stb,
                       self.in_accept, self.temp_z, self.temp_of,
                       self.out_z, self.out_norm)

        m.d.comb += self.stb.eq(norm_stb)
        m.d.sync += self.ack.eq(0) # sets to zero when not in normalise_1 state

        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        m.d.comb += self.in_accept.eq((~self.ack) & (self.stb))
        m.d.sync += self.temp_of.copy(self.mod.out_of)
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
            m.d.sync += self.out_roundz.eq(self.mod.out_of.roundz)


class FPNormToPack(FPState, FPID):

    def __init__(self, width, id_wid):
        FPID.__init__(self, id_wid)
        FPState.__init__(self, "normalise_1")
        self.width = width

    def setup(self, m, in_z, in_of, in_mid):
        """ links module to inputs and outputs
        """

        # Normalisation (chained to input in_z+in_of)
        nmod = FPNorm1ModSingle(self.width)
        n_out_z = FPNumBase(self.width)
        n_out_roundz = Signal(reset_less=True)
        nmod.setup(m, in_z, in_of, n_out_z)

        # Rounding (chained to normalisation)
        rmod = FPRoundMod(self.width)
        r_out_z = FPNumBase(self.width)
        rmod.setup(m, n_out_z, n_out_roundz)
        m.d.comb += n_out_roundz.eq(nmod.out_of.roundz)
        m.d.comb += r_out_z.copy(rmod.out_z)

        # Corrections (chained to rounding)
        cmod = FPCorrectionsMod(self.width)
        c_out_z = FPNumBase(self.width)
        cmod.setup(m, r_out_z)
        m.d.comb += c_out_z.copy(cmod.out_z)

        # Pack (chained to corrections)
        self.pmod = FPPackMod(self.width)
        self.out_z = FPNumBase(self.width)
        self.pmod.setup(m, c_out_z)

        # Multiplex ID
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m) # copies incoming ID to outgoing
        m.d.sync += self.out_z.v.eq(self.pmod.out_z.v) # outputs packed result
        m.next = "pack_put_z"


class FPRoundMod:

    def __init__(self, width):
        self.in_roundz = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.out_z = FPNumBase(width, False)

    def setup(self, m, in_z, roundz):
        m.submodules.roundz = self

        m.d.comb += self.in_z.copy(in_z)
        m.d.comb += self.in_roundz.eq(roundz)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.out_z.copy(self.in_z)
        with m.If(self.in_roundz):
            m.d.comb += self.out_z.m.eq(self.in_z.m + 1) # mantissa rounds up
            with m.If(self.in_z.m == self.in_z.m1s): # all 1s
                m.d.comb += self.out_z.e.eq(self.in_z.e + 1) # exponent up
        return m


class FPRound(FPState, FPID):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "round")
        FPID.__init__(self, id_wid)
        self.mod = FPRoundMod(width)
        self.out_z = FPNumBase(width)

    def setup(self, m, in_z, roundz, in_mid):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z, roundz)

        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        m.d.sync += self.out_z.copy(self.mod.out_z)
        m.next = "corrections"


class FPCorrectionsMod:

    def __init__(self, width):
        self.in_z = FPNumOut(width, False)
        self.out_z = FPNumOut(width, False)

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        m.submodules.corrections = self
        m.d.comb += self.in_z.copy(in_z)

    def elaborate(self, platform):
        m = Module()
        m.submodules.corr_in_z = self.in_z
        m.submodules.corr_out_z = self.out_z
        m.d.comb += self.out_z.copy(self.in_z)
        with m.If(self.in_z.is_denormalised):
            m.d.comb += self.out_z.e.eq(self.in_z.N127)
        return m


class FPCorrections(FPState, FPID):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "corrections")
        FPID.__init__(self, id_wid)
        self.mod = FPCorrectionsMod(width)
        self.out_z = FPNumBase(width)

    def setup(self, m, in_z, in_mid):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z)
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        m.d.sync += self.out_z.copy(self.mod.out_z)
        m.next = "pack"


class FPPackMod:

    def __init__(self, width):
        self.in_z = FPNumOut(width, False)
        self.out_z = FPNumOut(width, False)

    def setup(self, m, in_z):
        """ links module to inputs and outputs
        """
        m.submodules.pack = self
        m.d.comb += self.in_z.copy(in_z)

    def elaborate(self, platform):
        m = Module()
        m.submodules.pack_in_z = self.in_z
        with m.If(self.in_z.is_overflowed):
            m.d.comb += self.out_z.inf(self.in_z.s)
        with m.Else():
            m.d.comb += self.out_z.create(self.in_z.s, self.in_z.e, self.in_z.m)
        return m


class FPPack(FPState, FPID):

    def __init__(self, width, id_wid):
        FPState.__init__(self, "pack")
        FPID.__init__(self, id_wid)
        self.mod = FPPackMod(width)
        self.out_z = FPNumOut(width, False)

    def setup(self, m, in_z, in_mid):
        """ links module to inputs and outputs
        """
        self.mod.setup(m, in_z)
        if self.in_mid is not None:
            m.d.comb += self.in_mid.eq(in_mid)

    def action(self, m):
        self.idsync(m)
        m.d.sync += self.out_z.v.eq(self.mod.out_z.v)
        m.next = "pack_put_z"


class FPPutZ(FPState):

    def __init__(self, state, in_z, out_z, in_mid, out_mid):
        FPState.__init__(self, state)
        self.in_z = in_z
        self.out_z = out_z
        self.in_mid = in_mid
        self.out_mid = out_mid

    def action(self, m):
        if self.in_mid is not None:
            m.d.sync += self.out_mid.eq(self.in_mid)
        m.d.sync += [
          self.out_z.v.eq(self.in_z.v)
        ]
        with m.If(self.out_z.stb & self.out_z.ack):
            m.d.sync += self.out_z.stb.eq(0)
            m.next = "get_ops"
        with m.Else():
            m.d.sync += self.out_z.stb.eq(1)


class FPADDBaseMod(FPID):

    def __init__(self, width, id_wid=None, single_cycle=False, compact=True):
        """ IEEE754 FP Add

            * width: bit-width of IEEE754.  supported: 16, 32, 64
            * id_wid: an identifier that is sync-connected to the input
            * single_cycle: True indicates each stage to complete in 1 clock
            * compact: True indicates a reduced number of stages
        """
        FPID.__init__(self, id_wid)
        self.width = width
        self.single_cycle = single_cycle
        self.compact = compact

        self.in_t = Trigger()
        self.in_a  = Signal(width)
        self.in_b  = Signal(width)
        self.out_z = FPOp(width)

        self.states = []

    def add_state(self, state):
        self.states.append(state)
        return state

    def get_fragment(self, platform=None):
        """ creates the HDL code-fragment for FPAdd
        """
        m = Module()
        m.submodules.out_z = self.out_z
        m.submodules.in_t = self.in_t
        if self.compact:
            self.get_compact_fragment(m, platform)
        else:
            self.get_longer_fragment(m, platform)

        with m.FSM() as fsm:

            for state in self.states:
                with m.State(state.state_from):
                    state.action(m)

        return m

    def get_longer_fragment(self, m, platform=None):

        get = self.add_state(FPGet2Op("get_ops", "special_cases",
                                      self.in_a, self.in_b, self.width))
        get.setup(m, self.in_a, self.in_b, self.in_t.stb, self.in_t.ack)
        a = get.out_op1
        b = get.out_op2

        sc = self.add_state(FPAddSpecialCases(self.width, self.id_wid))
        sc.setup(m, a, b, self.in_mid)

        dn = self.add_state(FPAddDeNorm(self.width, self.id_wid))
        dn.setup(m, a, b, sc.in_mid)

        if self.single_cycle:
            alm = self.add_state(FPAddAlignSingle(self.width, self.id_wid))
            alm.setup(m, dn.out_a, dn.out_b, dn.in_mid)
        else:
            alm = self.add_state(FPAddAlignMulti(self.width, self.id_wid))
            alm.setup(m, dn.out_a, dn.out_b, dn.in_mid)

        add0 = self.add_state(FPAddStage0(self.width, self.id_wid))
        add0.setup(m, alm.out_a, alm.out_b, alm.in_mid)

        add1 = self.add_state(FPAddStage1(self.width, self.id_wid))
        add1.setup(m, add0.out_tot, add0.out_z, add0.in_mid)

        if self.single_cycle:
            n1 = self.add_state(FPNorm1Single(self.width, self.id_wid))
            n1.setup(m, add1.out_z, add1.out_of, add0.in_mid)
        else:
            n1 = self.add_state(FPNorm1Multi(self.width, self.id_wid))
            n1.setup(m, add1.out_z, add1.out_of, add1.norm_stb, add0.in_mid)

        rn = self.add_state(FPRound(self.width, self.id_wid))
        rn.setup(m, n1.out_z, n1.out_roundz, n1.in_mid)

        cor = self.add_state(FPCorrections(self.width, self.id_wid))
        cor.setup(m, rn.out_z, rn.in_mid)

        pa = self.add_state(FPPack(self.width, self.id_wid))
        pa.setup(m, cor.out_z, rn.in_mid)

        ppz = self.add_state(FPPutZ("pack_put_z", pa.out_z, self.out_z,
                                    pa.in_mid, self.out_mid))

        pz = self.add_state(FPPutZ("put_z", sc.out_z, self.out_z,
                                    pa.in_mid, self.out_mid))

    def get_compact_fragment(self, m, platform=None):

        get = self.add_state(FPGet2Op("get_ops", "special_cases",
                                      self.in_a, self.in_b, self.width))
        get.setup(m, self.in_a, self.in_b, self.in_t.stb, self.in_t.ack)
        a = get.out_op1
        b = get.out_op2

        sc = self.add_state(FPAddSpecialCasesDeNorm(self.width, self.id_wid))
        sc.setup(m, a, b, self.in_mid)

        if self.single_cycle:
            alm = self.add_state(FPAddAlignSingle(self.width, self.id_wid))
            alm.setup(m, sc.out_a, sc.out_b, sc.in_mid)
        else:
            alm = self.add_state(FPAddAlignMulti(self.width, self.id_wid))
            alm.setup(m, dn.out_a, dn.out_b, dn.in_mid)

        add0 = self.add_state(FPAddStage0(self.width, self.id_wid))
        add0.setup(m, alm.out_a, alm.out_b, alm.in_mid)

        add1 = self.add_state(FPAddStage1(self.width, self.id_wid))
        add1.setup(m, add0.out_tot, add0.out_z, add0.in_mid)

        n1 = self.add_state(FPNormToPack(self.width, self.id_wid))
        n1.setup(m, add1.out_z, add1.out_of, add0.in_mid)

        ppz = self.add_state(FPPutZ("pack_put_z", n1.out_z, self.out_z,
                                    n1.in_mid, self.out_mid))

        pz = self.add_state(FPPutZ("put_z", sc.out_z, self.out_z,
                                    sc.in_mid, self.out_mid))


class FPADDBase(FPState, FPID):

    def __init__(self, width, id_wid=None, single_cycle=False):
        """ IEEE754 FP Add

            * width: bit-width of IEEE754.  supported: 16, 32, 64
            * id_wid: an identifier that is sync-connected to the input
            * single_cycle: True indicates each stage to complete in 1 clock
        """
        FPID.__init__(self, id_wid)
        FPState.__init__(self, "fpadd")
        self.width = width
        self.single_cycle = single_cycle
        self.mod = FPADDBaseMod(width, id_wid, single_cycle)

        self.in_t = Trigger()
        self.in_a  = Signal(width)
        self.in_b  = Signal(width)
        #self.out_z = FPOp(width)

        self.z_done = Signal(reset_less=True) # connects to out_z Strobe
        self.in_accept = Signal(reset_less=True)
        self.add_stb = Signal(reset_less=True)
        self.add_ack = Signal(reset=0, reset_less=True)

    def setup(self, m, a, b, add_stb, in_mid, out_z, out_mid):
        self.out_z = out_z
        self.out_mid = out_mid
        m.d.comb += [self.in_a.eq(a),
                     self.in_b.eq(b),
                     self.mod.in_a.eq(self.in_a),
                     self.mod.in_b.eq(self.in_b),
                     self.in_mid.eq(in_mid),
                     self.mod.in_mid.eq(self.in_mid),
                     self.z_done.eq(self.mod.out_z.trigger),
                     #self.add_stb.eq(add_stb),
                     self.mod.in_t.stb.eq(self.in_t.stb),
                     self.in_t.ack.eq(self.mod.in_t.ack),
                     self.out_mid.eq(self.mod.out_mid),
                     self.out_z.v.eq(self.mod.out_z.v),
                     self.out_z.stb.eq(self.mod.out_z.stb),
                     self.mod.out_z.ack.eq(self.out_z.ack),
                    ]

        m.d.sync += self.add_stb.eq(add_stb)
        m.d.sync += self.add_ack.eq(0) # sets to zero when not in active state
        #m.d.sync += self.in_t.stb.eq(0)

        m.submodules.fpadd = self.mod

    def action(self, m):

        # in_accept is set on incoming strobe HIGH and ack LOW.
        m.d.comb += self.in_accept.eq((~self.add_ack) & (self.add_stb))

        #with m.If(self.in_t.ack):
        #    m.d.sync += self.in_t.stb.eq(0)
        with m.If(~self.z_done):
            # not done: test for accepting an incoming operand pair
            with m.If(self.in_accept):
                m.d.sync += [
                    self.add_ack.eq(1), # acknowledge receipt...
                    self.in_t.stb.eq(1), # initiate add
                ]
            with m.Else():
                m.d.sync += [self.add_ack.eq(0),
                             self.in_t.stb.eq(0),
                            ]
        with m.Else():
            # done: acknowledge, and write out id and value
            m.d.sync += [self.add_ack.eq(1),
                         self.in_t.stb.eq(0)
                        ]
            m.next = "get_a"

            return

            if self.in_mid is not None:
                m.d.sync += self.out_mid.eq(self.mod.out_mid)

            m.d.sync += [
              self.out_z.v.eq(self.mod.out_z.v)
            ]
            # move to output state on detecting z ack
            with m.If(self.out_z.trigger):
                m.d.sync += self.out_z.stb.eq(0)
                m.next = "put_z"
            with m.Else():
                m.d.sync += self.out_z.stb.eq(1)


class FPADD(FPID):
    """ FPADD: stages as follows:

        FPGetOp (a)
           |
        FPGetOp (b)
           |
        FPAddBase---> FPAddBaseMod
           |            |
        PutZ          GetOps->Specials->Align->Add1/2->Norm->Round/Pack->PutZ

        FPAddBase is tricky: it is both a stage and *has* stages.
        Connection to FPAddBaseMod therefore requires an in stb/ack
        and an out stb/ack.  Just as with Add1-Norm1 interaction, FPGetOp
        needs to be the thing that raises the incoming stb.
    """

    def __init__(self, width, id_wid=None, single_cycle=False):
        """ IEEE754 FP Add

            * width: bit-width of IEEE754.  supported: 16, 32, 64
            * id_wid: an identifier that is sync-connected to the input
            * single_cycle: True indicates each stage to complete in 1 clock
        """
        FPID.__init__(self, id_wid)
        self.width = width
        self.id_wid = id_wid
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
        m.submodules.in_a = self.in_a
        m.submodules.in_b = self.in_b
        m.submodules.out_z = self.out_z

        geta = self.add_state(FPGetOp("get_a", "get_b",
                                      self.in_a, self.width))
        geta.setup(m, self.in_a)
        a = geta.out_op

        getb = self.add_state(FPGetOp("get_b", "fpadd",
                                      self.in_b, self.width))
        getb.setup(m, self.in_b)
        b = getb.out_op

        ab = FPADDBase(self.width, self.id_wid, self.single_cycle)
        ab = self.add_state(ab)
        ab.setup(m, a, b, getb.out_decode, self.in_mid,
                 self.out_z, self.out_mid)

        #pz = self.add_state(FPPutZ("put_z", ab.out_z, self.out_z,
        #                            ab.out_mid, self.out_mid))

        with m.FSM() as fsm:

            for state in self.states:
                with m.State(state.state_from):
                    state.action(m)

        return m


if __name__ == "__main__":
    if True:
        alu = FPADD(width=32, id_wid=5, single_cycle=True)
        main(alu, ports=alu.in_a.ports() + \
                        alu.in_b.ports() + \
                        alu.out_z.ports() + \
                        [alu.in_mid, alu.out_mid])
    else:
        alu = FPADDBase(width=32, id_wid=5, single_cycle=True)
        main(alu, ports=[alu.in_a, alu.in_b] + \
                        alu.in_t.ports() + \
                        alu.out_z.ports() + \
                        [alu.in_mid, alu.out_mid])


    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                        ports=alu.in_a.ports() + \
    #                              alu.in_b.ports() + \
    #                              alu.out_z.ports())

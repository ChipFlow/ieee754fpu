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


class FPGetOpA(FPState):
    """ gets operand a
    """

    def __init__(self, in_a, width):
        FPState.__init__(self, "get_a")
        self.in_a = in_a
        self.a = FPNumIn(in_a, width)

    def action(self, m):
        self.get_op(m, self.in_a, self.a, "get_b")


class FPGetOpB(FPState):
    """ gets operand b
    """

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
            m.d.comb += self.out_z.nan(1)

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
                m.d.comb += self.out_z.nan(1)

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


class FPAddDeNorm(FPState):

    def action(self, m):
        # Denormalised Number checks
        m.next = "align"
        self.denormalise(m, self.a)
        self.denormalise(m, self.b)


class FPAddAlignMulti(FPState):

    def action(self, m):
        # NOTE: this does *not* do single-cycle multi-shifting,
        #       it *STAYS* in the align state until exponents match

        # exponent of a greater than b: shift b down
        with m.If(self.a.e > self.b.e):
            m.d.sync += self.b.shift_down()
        # exponent of b greater than a: shift a down
        with m.Elif(self.a.e < self.b.e):
            m.d.sync += self.a.shift_down()
        # exponents equal: move to next stage.
        with m.Else():
            m.next = "add_0"


class FPAddAlignSingle(FPState):

    def action(self, m):
        # This one however (single-cycle) will do the shift
        # in one go.

        # XXX TODO: the shifter used here is quite expensive
        # having only one would be better

        ediff = Signal((len(self.a.e), True), reset_less=True)
        ediffr = Signal((len(self.a.e), True), reset_less=True)
        m.d.comb += ediff.eq(self.a.e - self.b.e)
        m.d.comb += ediffr.eq(self.b.e - self.a.e)
        with m.If(ediff > 0):
            m.d.sync += self.b.shift_down_multi(ediff)
        # exponent of b greater than a: shift a down
        with m.Elif(ediff < 0):
            m.d.sync += self.a.shift_down_multi(ediffr)

        m.next = "add_0"


class FPAddStage0(FPState):
    """ First stage of add.  covers same-sign (add) and subtract
        special-casing when mantissas are greater or equal, to
        give greatest accuracy.
    """

    def action(self, m):
        m.next = "add_1"
        m.d.sync += self.z.e.eq(self.a.e)
        # same-sign (both negative or both positive) add mantissas
        with m.If(self.a.s == self.b.s):
            m.d.sync += [
                self.tot.eq(Cat(self.a.m, 0) + Cat(self.b.m, 0)),
                self.z.s.eq(self.a.s)
            ]
        # a mantissa greater than b, use a
        with m.Elif(self.a.m >= self.b.m):
            m.d.sync += [
                self.tot.eq(Cat(self.a.m, 0) - Cat(self.b.m, 0)),
                self.z.s.eq(self.a.s)
            ]
        # b mantissa greater than a, use b
        with m.Else():
            m.d.sync += [
                self.tot.eq(Cat(self.b.m, 0) - Cat(self.a.m, 0)),
                self.z.s.eq(self.b.s)
        ]


class FPAddStage1(FPState):
    """ Second stage of add: preparation for normalisation.
        detects when tot sum is too big (tot[27] is kinda a carry bit)
    """

    def action(self, m):
        m.next = "normalise_1"
        # tot[27] gets set when the sum overflows. shift result down
        with m.If(self.tot[-1]):
            m.d.sync += [
                self.z.m.eq(self.tot[4:]),
                self.of.m0.eq(self.tot[4]),
                self.of.guard.eq(self.tot[3]),
                self.of.round_bit.eq(self.tot[2]),
                self.of.sticky.eq(self.tot[1] | self.tot[0]),
                self.z.e.eq(self.z.e + 1)
        ]
        # tot[27] zero case
        with m.Else():
            m.d.sync += [
                self.z.m.eq(self.tot[3:]),
                self.of.m0.eq(self.tot[3]),
                self.of.guard.eq(self.tot[2]),
                self.of.round_bit.eq(self.tot[1]),
                self.of.sticky.eq(self.tot[0])
        ]


class FPNorm1Mod:

    def __init__(self, width):
        self.out_norm = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.out_z = FPNumBase(width, False)
        self.in_of = Overflow()
        self.out_of = Overflow()

    def setup(self, m, in_z, out_z, in_of, out_of, out_norm):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_z.copy(in_z)
        m.d.comb += out_z.copy(self.out_z)
        m.d.comb += self.in_of.copy(in_of)
        m.d.comb += out_of.copy(self.out_of)
        m.d.comb += out_norm.eq(self.out_norm)

    def elaborate(self, platform):
        m = Module()
        m.submodules.norm1_in_overflow = self.in_of
        m.submodules.norm1_out_overflow = self.out_of
        m.submodules.norm1_in_z = self.in_z
        m.submodules.norm1_out_z = self.out_z
        m.d.comb += self.out_z.copy(self.in_z)
        m.d.comb += self.out_of.copy(self.in_of)
        m.d.comb += self.out_norm.eq((self.in_z.m_msbzero) & \
                                     (self.in_z.exp_gt_n126))
        with m.If(self.out_norm):
            m.d.comb += [
                self.out_z.e.eq(self.in_z.e - 1),  # DECREASE exponent
                self.out_z.m.eq(self.in_z.m << 1), # shift mantissa UP
                self.out_z.m[0].eq(self.in_of.guard), # steal guard (was tot[2])
                self.out_of.guard.eq(self.in_of.round_bit), # round (was tot[1])
                self.out_of.round_bit.eq(0),        # reset round bit
                self.out_of.m0.eq(self.in_of.guard),
            ]

        return m


class FPNorm1(FPState):

    def __init__(self, width):
        FPState.__init__(self, "normalise_1")
        self.mod = FPNorm1Mod(width)
        self.out_norm = Signal(reset_less=True)
        self.out_z = FPNumBase(width)
        self.out_of = Overflow()

    def action(self, m):
        m.d.sync += self.of.copy(self.out_of)
        m.d.sync += self.z.copy(self.out_z)
        with m.If(~self.out_norm):
            m.next = "normalise_2"


class FPNorm2Mod:

    def __init__(self, width):
        self.out_norm = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.out_z = FPNumBase(width, False)
        self.in_of = Overflow()
        self.out_of = Overflow()

    def setup(self, m, in_z, out_z, in_of, out_of, out_norm):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_z.copy(in_z)
        m.d.comb += out_z.copy(self.out_z)
        m.d.comb += self.in_of.copy(in_of)
        m.d.comb += out_of.copy(self.out_of)
        m.d.comb += out_norm.eq(self.out_norm)

    def elaborate(self, platform):
        m = Module()
        m.submodules.norm1_in_overflow = self.in_of
        m.submodules.norm1_out_overflow = self.out_of
        m.submodules.norm1_in_z = self.in_z
        m.submodules.norm1_out_z = self.out_z
        m.d.comb += self.out_z.copy(self.in_z)
        m.d.comb += self.out_of.copy(self.in_of)
        m.d.comb += self.out_norm.eq(self.in_z.exp_lt_n126)
        with m.If(self.out_norm):
            m.d.comb += [
                self.out_z.e.eq(self.in_z.e + 1),  # INCREASE exponent
                self.out_z.m.eq(self.in_z.m >> 1), # shift mantissa DOWN
                self.out_of.guard.eq(self.in_z.m[0]),
                self.out_of.m0.eq(self.in_z.m[1]),
                self.out_of.round_bit.eq(self.in_of.guard),
                self.out_of.sticky.eq(self.in_of.sticky | self.in_of.round_bit)
            ]

        return m


class FPNorm2(FPState):

    def __init__(self, width):
        FPState.__init__(self, "normalise_2")
        self.mod = FPNorm2Mod(width)
        self.out_norm = Signal(reset_less=True)
        self.out_z = FPNumBase(width)
        self.out_of = Overflow()

    def action(self, m):
        m.d.sync += self.of.copy(self.out_of)
        m.d.sync += self.z.copy(self.out_z)
        with m.If(~self.out_norm):
            m.next = "round"


class FPRoundMod:

    def __init__(self, width):
        self.in_roundz = Signal(reset_less=True)
        self.in_z = FPNumBase(width, False)
        self.out_z = FPNumBase(width, False)

    def setup(self, m, in_z, out_z, in_of):
        """ links module to inputs and outputs
        """
        m.d.comb += self.in_z.copy(in_z)
        m.d.comb += out_z.copy(self.out_z)
        m.d.comb += self.in_roundz.eq(in_of.roundz)

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
        m.next = "put_z"


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
        #a = FPNumIn(self.in_a, self.width)
        b = FPNumIn(self.in_b, self.width)
        z = FPNumOut(self.width, False)

        m.submodules.fpnum_b = b
        m.submodules.fpnum_z = z

        w = z.m_width + 4
        tot = Signal(w, reset_less=True) # sticky/round/guard, {mantissa} result, 1 overflow

        of = Overflow()
        m.submodules.overflow = of

        geta = self.add_state(FPGetOpA(self.in_a, self.width))
        #geta.set_inputs({"in_a": self.in_a})
        #geta.set_outputs({"a": a})
        a = geta.a
        # XXX m.d.comb += a.v.eq(self.in_a.v) # links in_a to a
        m.submodules.fpnum_a = a

        getb = self.add_state(FPGetOpB("get_b"))
        getb.set_inputs({"in_b": self.in_b})
        getb.set_outputs({"b": b})
        # XXX m.d.comb += b.v.eq(self.in_b.v) # links in_b to b

        sc = self.add_state(FPAddSpecialCases(self.width))
        sc.set_inputs({"a": a, "b": b})
        sc.set_outputs({"z": z})
        sc.mod.setup(m, a, b, sc.out_z, sc.out_do_z)
        m.submodules.specialcases = sc.mod

        dn = self.add_state(FPAddDeNorm("denormalise"))
        dn.set_inputs({"a": a, "b": b})
        dn.set_outputs({"a": a, "b": b}) # XXX outputs same as inputs

        if self.single_cycle:
            alm = self.add_state(FPAddAlignSingle("align"))
        else:
            alm = self.add_state(FPAddAlignMulti("align"))
        alm.set_inputs({"a": a, "b": b})
        alm.set_outputs({"a": a, "b": b}) # XXX outputs same as inputs

        add0 = self.add_state(FPAddStage0("add_0"))
        add0.set_inputs({"a": a, "b": b})
        add0.set_outputs({"z": z, "tot": tot})

        add1 = self.add_state(FPAddStage1("add_1"))
        add1.set_inputs({"tot": tot, "z": z}) # Z input passes through
        add1.set_outputs({"z": z, "of": of})  # XXX Z as output

        n1 = self.add_state(FPNorm1(self.width))
        n1.set_inputs({"z": z, "of": of})  # XXX Z as output
        n1.set_outputs({"z": z})  # XXX Z as output
        n1.mod.setup(m, z, n1.out_z, of, n1.out_of, n1.out_norm)
        m.submodules.normalise_1 = n1.mod

        n2 = self.add_state(FPNorm2(self.width))
        n2.set_inputs({"z": z, "of": of})  # XXX Z as output
        n2.set_outputs({"z": z})  # XXX Z as output
        n2.mod.setup(m, z, n2.out_z, of, n2.out_of, n2.out_norm)
        m.submodules.normalise_2 = n2.mod

        rn = self.add_state(FPRound(self.width))
        rn.set_inputs({"z": z, "of": of})  # XXX Z as output
        rn.set_outputs({"z": z})  # XXX Z as output
        rn.mod.setup(m, z, rn.out_z, of)
        m.submodules.roundz = rn.mod

        cor = self.add_state(FPCorrections(self.width))
        cor.set_inputs({"z": z})  # XXX Z as output
        cor.set_outputs({"z": z})  # XXX Z as output
        cor.mod.setup(m, z, cor.out_z)
        m.submodules.corrections = cor.mod

        pa = self.add_state(FPPack(self.width))
        pa.set_inputs({"z": z})  # XXX Z as output
        pa.set_outputs({"z": z})  # XXX Z as output
        pa.mod.setup(m, z, pa.out_z)
        m.submodules.pack = pa.mod

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

# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat
from nmigen.cli import main, verilog

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase


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

    def action(self, m):
        self.get_op(m, self.in_a, self.a, "get_b")


class FPGetOpB(FPState):
    """ gets operand b
    """

    def action(self, m):
        self.get_op(m, self.in_b, self.b, "special_cases")


class FPAddSpecialCases(FPState):
    """ special cases: NaNs, infs, zeros, denormalised
        NOTE: some of these are unique to add.  see "Special Operations"
        https://steve.hollasch.net/cgindex/coding/ieeefloat.html
    """

    def action(self, m):
        s_nomatch = Signal()
        m.d.comb += s_nomatch.eq(self.a.s != self.b.s)

        m_match = Signal()
        m.d.comb += m_match.eq(self.a.m == self.b.m)

        # if a is NaN or b is NaN return NaN
        with m.If(self.a.is_nan | self.b.is_nan):
            m.next = "put_z"
            m.d.sync += self.z.nan(1)

        # XXX WEIRDNESS for FP16 non-canonical NaN handling
        # under review

        ## if a is zero and b is NaN return -b
        #with m.If(a.is_zero & (a.s==0) & b.is_nan):
        #    m.next = "put_z"
        #    m.d.sync += z.create(b.s, b.e, Cat(b.m[3:-2], ~b.m[0]))

        ## if b is zero and a is NaN return -a
        #with m.Elif(b.is_zero & (b.s==0) & a.is_nan):
        #    m.next = "put_z"
        #    m.d.sync += z.create(a.s, a.e, Cat(a.m[3:-2], ~a.m[0]))

        ## if a is -zero and b is NaN return -b
        #with m.Elif(a.is_zero & (a.s==1) & b.is_nan):
        #    m.next = "put_z"
        #    m.d.sync += z.create(a.s & b.s, b.e, Cat(b.m[3:-2], 1))

        ## if b is -zero and a is NaN return -a
        #with m.Elif(b.is_zero & (b.s==1) & a.is_nan):
        #    m.next = "put_z"
        #    m.d.sync += z.create(a.s & b.s, a.e, Cat(a.m[3:-2], 1))

        # if a is inf return inf (or NaN)
        with m.Elif(self.a.is_inf):
            m.next = "put_z"
            m.d.sync += self.z.inf(self.a.s)
            # if a is inf and signs don't match return NaN
            with m.If(self.b.exp_128 & s_nomatch):
                m.d.sync += self.z.nan(1)

        # if b is inf return inf
        with m.Elif(self.b.is_inf):
            m.next = "put_z"
            m.d.sync += self.z.inf(self.b.s)

        # if a is zero and b zero return signed-a/b
        with m.Elif(self.a.is_zero & self.b.is_zero):
            m.next = "put_z"
            m.d.sync += self.z.create(self.a.s & self.b.s, self.b.e,
                                      self.b.m[3:-1])

        # if a is zero return b
        with m.Elif(self.a.is_zero):
            m.next = "put_z"
            m.d.sync += self.z.create(self.b.s, self.b.e, self.b.m[3:-1])

        # if b is zero return a
        with m.Elif(self.b.is_zero):
            m.next = "put_z"
            m.d.sync += self.z.create(self.a.s, self.a.e, self.a.m[3:-1])

        # if a equal to -b return zero (+ve zero)
        with m.Elif(s_nomatch & m_match & (self.a.e == self.b.e)):
            m.next = "put_z"
            m.d.sync += self.z.zero(0)

        # Denormalised Number checks
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


class FPNorm1(FPState):

    def action(self, m):
        self.normalise_1(m, self.z, self.of, "normalise_2")


class FPNorm2(FPState):

    def action(self, m):
        self.normalise_2(m, self.z, self.of, "round")


class FPRound(FPState):

    def action(self, m):
        self.roundz(m, self.z, self.of, "corrections")


class FPCorrections(FPState):

    def action(self, m):
        self.corrections(m, self.z, "pack")


class FPPack(FPState):

    def action(self, m):
        self.pack(m, self.z, "put_z")


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
        a = FPNumIn(self.in_a, self.width)
        b = FPNumIn(self.in_b, self.width)
        z = FPNumOut(self.width, False)

        m.submodules.fpnum_a = a
        m.submodules.fpnum_b = b
        m.submodules.fpnum_z = z

        w = z.m_width + 4
        tot = Signal(w, reset_less=True) # sticky/round/guard, {mantissa} result, 1 overflow

        of = Overflow()
        m.submodules.overflow = of

        geta = self.add_state(FPGetOpA("get_a"))
        geta.set_inputs({"in_a": self.in_a})
        geta.set_outputs({"a": a})
        m.d.comb += a.v.eq(self.in_a.v) # links in_a to a

        getb = self.add_state(FPGetOpB("get_b"))
        getb.set_inputs({"in_b": self.in_b})
        getb.set_outputs({"b": b})
        m.d.comb += b.v.eq(self.in_b.v) # links in_b to b

        sc = self.add_state(FPAddSpecialCases("special_cases"))
        sc.set_inputs({"a": a, "b": b})
        sc.set_outputs({"z": z})

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

        n1 = self.add_state(FPNorm1("normalise_1"))
        n1.set_inputs({"z": z, "of": of})  # XXX Z as output
        n1.set_outputs({"z": z})  # XXX Z as output

        n2 = self.add_state(FPNorm2("normalise_2"))
        n2.set_inputs({"z": z, "of": of})  # XXX Z as output
        n2.set_outputs({"z": z})  # XXX Z as output

        rn = self.add_state(FPRound("round"))
        rn.set_inputs({"z": z, "of": of})  # XXX Z as output
        rn.set_outputs({"z": z})  # XXX Z as output

        cor = self.add_state(FPCorrections("corrections"))
        cor.set_inputs({"z": z})  # XXX Z as output
        cor.set_outputs({"z": z})  # XXX Z as output

        pa = self.add_state(FPPack("pack"))
        pa.set_inputs({"z": z})  # XXX Z as output
        pa.set_outputs({"z": z})  # XXX Z as output

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

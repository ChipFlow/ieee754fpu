# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat, Elaboratable
from nmigen.cli import main, verilog

from ieee754.fpcommon.fpbase import (FPNumIn, FPNumOut, FPOpIn,
                                     FPOpOut, Overflow, FPBase,
                                     FPNumBaseRecord)

from nmutil.nmoperator import eq


class FPADD(FPBase, Elaboratable):

    def __init__(self, width, single_cycle=False):
        FPBase.__init__(self)
        self.width = width
        self.single_cycle = single_cycle

        self.in_a  = FPOpIn(width)
        self.in_a.data_i = Signal(width)
        self.in_b  = FPOpIn(width)
        self.in_b.data_i = Signal(width)
        self.out_z = FPOpOut(width)
        self.out_z.data_o = Signal(width)

    def elaborate(self, platform=None):
        """ creates the HDL code-fragment for FPAdd
        """
        m = Module()

        # Latches
        a = FPNumBaseRecord(self.width, False)
        b = FPNumBaseRecord(self.width, False)
        z = FPNumBaseRecord(self.width, False)
        a = FPNumIn(None, a)
        b = FPNumIn(None, b)
        z = FPNumOut(z)

        m.submodules.fpnum_a = a
        m.submodules.fpnum_b = b
        m.submodules.fpnum_z = z

        m.d.comb += a.v.eq(self.in_a.v)
        m.d.comb += b.v.eq(self.in_b.v)

        w = z.m_width + 4 # sticky/round/guard, {mantissa} result, 1 overflow
        tot = Signal(w, reset_less=True)

        of = Overflow()

        with m.FSM() as fsm:

            # ******
            # gets operand a

            with m.State("get_a"):
                res = self.get_op(m, self.in_a, a, "get_b")
                m.d.sync += eq([a, self.in_a.ready_o], res)

            # ******
            # gets operand b

            with m.State("get_b"):
                res = self.get_op(m, self.in_b, b, "special_cases")
                m.d.sync += eq([b, self.in_b.ready_o], res)

            # ******
            # special cases: NaNs, infs, zeros, denormalised
            # NOTE: some of these are unique to add.  see "Special Operations"
            # https://steve.hollasch.net/cgindex/coding/ieeefloat.html

            with m.State("special_cases"):

                s_nomatch = Signal()
                m.d.comb += s_nomatch.eq(a.s != b.s)

                m_match = Signal()
                m.d.comb += m_match.eq(a.m == b.m)

                # if a is NaN or b is NaN return NaN
                with m.If(a.is_nan | b.is_nan):
                    m.next = "put_z"
                    m.d.sync += z.nan(1)

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
                with m.Elif(a.is_inf):
                    m.next = "put_z"
                    m.d.sync += z.inf(a.s)
                    # if a is inf and signs don't match return NaN
                    with m.If(b.exp_128 & s_nomatch):
                        m.d.sync += z.nan(1)

                # if b is inf return inf
                with m.Elif(b.is_inf):
                    m.next = "put_z"
                    m.d.sync += z.inf(b.s)

                # if a is zero and b zero return signed-a/b
                with m.Elif(a.is_zero & b.is_zero):
                    m.next = "put_z"
                    m.d.sync += z.create(a.s & b.s, b.e, b.m[3:-1])

                # if a is zero return b
                with m.Elif(a.is_zero):
                    m.next = "put_z"
                    m.d.sync += z.create(b.s, b.e, b.m[3:-1])

                # if b is zero return a
                with m.Elif(b.is_zero):
                    m.next = "put_z"
                    m.d.sync += z.create(a.s, a.e, a.m[3:-1])

                # if a equal to -b return zero (+ve zero)
                with m.Elif(s_nomatch & m_match & (a.e == b.e)):
                    m.next = "put_z"
                    m.d.sync += z.zero(0)

                # Denormalised Number checks
                with m.Else():
                    m.next = "align"
                    self.denormalise(m, a)
                    self.denormalise(m, b)

            # ******
            # align.

            with m.State("align"):
                if not self.single_cycle:
                    # NOTE: this does *not* do single-cycle multi-shifting,
                    #       it *STAYS* in the align state until exponents match

                    # exponent of a greater than b: shift b down
                    with m.If(a.e > b.e):
                        m.d.sync += b.shift_down(b)
                    # exponent of b greater than a: shift a down
                    with m.Elif(a.e < b.e):
                        m.d.sync += a.shift_down(a)
                    # exponents equal: move to next stage.
                    with m.Else():
                        m.next = "add_0"
                else:
                    # This one however (single-cycle) will do the shift
                    # in one go.

                    # XXX TODO: the shifter used here is quite expensive
                    # having only one would be better

                    ediff = Signal((len(a.e), True), reset_less=True)
                    ediffr = Signal((len(a.e), True), reset_less=True)
                    m.d.comb += ediff.eq(a.e - b.e)
                    m.d.comb += ediffr.eq(b.e - a.e)
                    with m.If(ediff > 0):
                        m.d.sync += b.shift_down_multi(ediff)
                    # exponent of b greater than a: shift a down
                    with m.Elif(ediff < 0):
                        m.d.sync += a.shift_down_multi(ediffr)

                    m.next = "add_0"

            # ******
            # First stage of add.  covers same-sign (add) and subtract
            # special-casing when mantissas are greater or equal, to
            # give greatest accuracy.

            with m.State("add_0"):
                m.next = "add_1"
                m.d.sync += z.e.eq(a.e)
                # same-sign (both negative or both positive) add mantissas
                with m.If(a.s == b.s):
                    m.d.sync += [
                        tot.eq(Cat(a.m, 0) + Cat(b.m, 0)),
                        z.s.eq(a.s)
                    ]
                # a mantissa greater than b, use a
                with m.Elif(a.m >= b.m):
                    m.d.sync += [
                        tot.eq(Cat(a.m, 0) - Cat(b.m, 0)),
                        z.s.eq(a.s)
                    ]
                # b mantissa greater than a, use b
                with m.Else():
                    m.d.sync += [
                        tot.eq(Cat(b.m, 0) - Cat(a.m, 0)),
                        z.s.eq(b.s)
                ]

            # ******
            # Second stage of add: preparation for normalisation.
            # detects when tot sum is too big (tot[27] is kinda a carry bit)

            with m.State("add_1"):
                m.next = "normalise_1"
                # tot[27] gets set when the sum overflows. shift result down
                with m.If(tot[-1]):
                    m.d.sync += [
                        z.m.eq(tot[4:]),
                        of.m0.eq(tot[4]),
                        of.guard.eq(tot[3]),
                        of.round_bit.eq(tot[2]),
                        of.sticky.eq(tot[1] | tot[0]),
                        z.e.eq(z.e + 1)
                ]
                # tot[27] zero case
                with m.Else():
                    m.d.sync += [
                        z.m.eq(tot[3:]),
                        of.m0.eq(tot[3]),
                        of.guard.eq(tot[2]),
                        of.round_bit.eq(tot[1]),
                        of.sticky.eq(tot[0])
                ]

            # ******
            # First stage of normalisation.

            with m.State("normalise_1"):
                self.normalise_1(m, z, of, "normalise_2")

            # ******
            # Second stage of normalisation.

            with m.State("normalise_2"):
                self.normalise_2(m, z, of, "round")

            # ******
            # rounding stage

            with m.State("round"):
                self.roundz(m, z, of.roundz)
                m.next = "corrections"

            # ******
            # correction stage

            with m.State("corrections"):
                self.corrections(m, z, "pack")

            # ******
            # pack stage

            with m.State("pack"):
                self.pack(m, z, "put_z")

            # ******
            # put_z stage

            with m.State("put_z"):
                self.put_z(m, z, self.out_z, "get_a")

        return m


if __name__ == "__main__":
    alu = FPADD(width=32)
    main(alu, ports=alu.in_a.ports() + alu.in_b.ports() + alu.out_z.ports())


    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                        ports=alu.in_a.ports() + \
    #                              alu.in_b.ports() + \
    #                              alu.out_z.ports())

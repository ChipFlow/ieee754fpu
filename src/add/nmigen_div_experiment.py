# IEEE Floating Point Divider (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Const, Cat
from nmigen.cli import main, verilog

from fpbase import FPNum, FPOp, Overflow, FPBase

class Div:
    def __init__(self, width):
        self.width = width
        self.quotient = Signal(width)
        self.divisor = Signal(width)
        self.dividend = Signal(width)
        self.remainder = Signal(width)
        self.count = Signal(6)

        self.czero = Const(0, width)

    def reset(self, m):
        m.d.sync += [
            self.quotient.eq(self.czero),
            self.remainder.eq(self.czero),
            self.count.eq(Const(0, 6))
        ]


class FPDIV(FPBase):

    def __init__(self, width):
        FPBase.__init__(self)
        self.width = width

        self.in_a  = FPOp(width)
        self.in_b  = FPOp(width)
        self.out_z = FPOp(width)

    def get_fragment(self, platform=None):
        """ creates the HDL code-fragment for FPDiv
        """
        m = Module()

        # Latches
        a = FPNum(self.width, 24)
        b = FPNum(self.width, 24)
        z = FPNum(self.width, 24)

        div = Div(51)

        of = Overflow()

        with m.FSM() as fsm:

            # ******
            # gets operand a

            with m.State("get_a"):
                self.get_op(m, self.in_a, a, "get_b")

            # ******
            # gets operand b

            with m.State("get_b"):
                self.get_op(m, self.in_b, b, "special_cases")

            # ******
            # special cases: NaNs, infs, zeros, denormalised
            # NOTE: some of these are unique to div.  see "Special Operations"
            # https://steve.hollasch.net/cgindex/coding/ieeefloat.html

            with m.State("special_cases"):

                # if a is NaN or b is NaN return NaN
                with m.If(a.is_nan() | b.is_nan()):
                    m.next = "put_z"
                    m.d.sync += z.nan(1)

                # if a is Inf and b is Inf return NaN
                with m.Elif(a.is_inf() | b.is_inf()):
                    m.next = "put_z"
                    m.d.sync += z.nan(1)

                # if a is inf return inf (or NaN if b is zero)
                with m.Elif(a.is_inf()):
                    m.next = "put_z"
                    # if b is zero return NaN
                    with m.If(b.is_zero()):
                        m.d.sync += z.nan(1)
                    with m.Else():
                        m.d.sync += z.inf(a.s ^ b.s)

                # if b is inf return zero
                with m.Elif(b.is_inf()):
                    m.next = "put_z"
                    m.d.sync += z.zero(a.s ^ b.s)

                # if a is inf return zero (or NaN if b is zero)
                with m.Elif(a.is_inf()):
                    m.next = "put_z"
                    # if b is zero return NaN
                    with m.If(b.is_zero()):
                        m.d.sync += z.nan(1)
                    with m.Else():
                        m.d.sync += z.inf(a.s ^ b.s)

                # if b is zero return Inf
                with m.Elif(b.is_zero()):
                    m.next = "put_z"
                    m.d.sync += z.zero(a.s ^ b.s)

                # Denormalised Number checks
                with m.Else():
                    m.next = "normalise_a"
                    self.denormalise(m, a)
                    self.denormalise(m, b)

            # ******
            # normalise_a

            with m.State("normalise_a"):
                self.op_normalise(m, a, "normalise_b")

            # ******
            # normalise_b

            with m.State("normalise_b"):
                self.op_normalise(m, b, "divide_0")

            # ******
            # First stage of divide.  initialise state

            with m.State("divide_0"):
                m.next = "divide_1"
                m.d.sync += [
                    z.s.eq(a.s ^ b.s), # sign
                    z.e.eq(a.e - b.e), # exponent
                    div.dividend.eq(a.m<<27),
                    div.divisor.eq(b.m),
                ]
                div.reset(m)

            # ******
            # Second stage of divide.

            with m.State("divide_1"):
                m.next = "divide_2"
                m.d.sync += [
                    div.quotient.eq(div.quotient << 1),
                    div.remainder.eq(Cat(div.dividend[50], div.remainder[0:])),
                    div.dividend.eq(div.dividend << 1),
                ]

            # ******
            # Third stage of divide.

            with m.State("divide_2"):
                with m.If(div.remainder >= div.divisor):
                    m.d.sync += [
                        div.quotient[0].eq(1),
                        div.remainder.eq(div.remainder - div.divisor),
                    ]
                with m.If(div.count == div.width-2):
                    m.next = "divide_3"
                with m.Else():
                    m.next = "divide_1"
                    m.d.sync += [
                        div.count.eq(div.count + 1),
                    ]

            # ******
            # Fourth stage of divide.

            with m.State("divide_3"):
                m.next = "normalise_1"
                m.d.sync += [
                    z.m.eq(div.quotient[3:27]),
                    of.guard.eq(div.quotient[2]),
                    of.round_bit.eq(div.quotient[1]),
                    of.sticky.eq(div.quotient[0] | (div.remainder != 0))
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
                self.roundz(m, z, of, "corrections")

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
    alu = FPDIV(width=32)
    main(alu, ports=alu.in_a.ports() + alu.in_b.ports() + alu.out_z.ports())


    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                        ports=alu.in_a.ports() + \
    #                              alu.in_b.ports() + \
    #                              alu.out_z.ports())

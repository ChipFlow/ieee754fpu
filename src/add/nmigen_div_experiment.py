# IEEE Floating Point Divider (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Const, Cat
from nmigen.cli import main, verilog

from fpbase import FPNumIn, FPNumOut, FPOp, Overflow, FPBase
from nmigen_add_experiment import FPState

class Div:
    def __init__(self, width):
        self.width = width
        self.quot = Signal(width)  # quotient
        self.dor = Signal(width)   # divisor
        self.dend = Signal(width)  # dividend
        self.rem = Signal(width)   # remainder
        self.count = Signal(7)     # loop count

        self.czero = Const(0, width)

    def reset(self, m):
        m.d.sync += [
            self.quot.eq(self.czero),
            self.rem.eq(self.czero),
            self.count.eq(Const(0, 7))
        ]


class FPDIV(FPBase):

    def __init__(self, width):
        FPBase.__init__(self)
        self.width = width

        self.in_a  = FPOp(width)
        self.in_b  = FPOp(width)
        self.out_z = FPOp(width)

        self.states = []

    def add_state(self, state):
        self.states.append(state)
        return state

    def get_fragment(self, platform=None):
        """ creates the HDL code-fragment for FPDiv
        """
        m = Module()

        # Latches
        a = FPNumIn(None, self.width, False)
        b = FPNumIn(None, self.width, False)
        z = FPNumOut(self.width, False)

        div = Div(a.m_width*2 + 3) # double the mantissa width plus g/r/sticky

        of = Overflow()
        m.submodules.in_a = a
        m.submodules.in_b = b
        m.submodules.z = z
        m.submodules.of = of

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
                with m.If(a.is_nan | b.is_nan):
                    m.next = "put_z"
                    m.d.sync += z.nan(1)

                # if a is Inf and b is Inf return NaN
                with m.Elif(a.is_inf & b.is_inf):
                    m.next = "put_z"
                    m.d.sync += z.nan(1)

                # if a is inf return inf (or NaN if b is zero)
                with m.Elif(a.is_inf):
                    m.next = "put_z"
                    m.d.sync += z.inf(a.s ^ b.s)

                # if b is inf return zero
                with m.Elif(b.is_inf):
                    m.next = "put_z"
                    m.d.sync += z.zero(a.s ^ b.s)

                # if a is zero return zero (or NaN if b is zero)
                with m.Elif(a.is_zero):
                    m.next = "put_z"
                    # if b is zero return NaN
                    with m.If(b.is_zero):
                        m.d.sync += z.nan(1)
                    with m.Else():
                        m.d.sync += z.zero(a.s ^ b.s)

                # if b is zero return Inf
                with m.Elif(b.is_zero):
                    m.next = "put_z"
                    m.d.sync += z.inf(a.s ^ b.s)

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
                    div.dend.eq(a.m<<(a.m_width+3)), # 3 bits for g/r/sticky
                    div.dor.eq(b.m),
                ]
                div.reset(m)

            # ******
            # Second stage of divide.

            with m.State("divide_1"):
                m.next = "divide_2"
                m.d.sync += [
                    div.quot.eq(div.quot << 1),
                    div.rem.eq(Cat(div.dend[-1], div.rem[0:])),
                    div.dend.eq(div.dend << 1),
                ]

            # ******
            # Third stage of divide.
            # This stage ends by jumping out to divide_3
            # However it defaults to jumping to divide_1 (which comes back here)

            with m.State("divide_2"):
                with m.If(div.rem >= div.dor):
                    m.d.sync += [
                        div.quot[0].eq(1),
                        div.rem.eq(div.rem - div.dor),
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
                    z.m.eq(div.quot[3:]),
                    of.guard.eq(div.quot[2]),
                    of.round_bit.eq(div.quot[1]),
                    of.sticky.eq(div.quot[0] | (div.rem != 0))
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
    alu = FPDIV(width=32)
    main(alu, ports=alu.in_a.ports() + alu.in_b.ports() + alu.out_z.ports())


    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                        ports=alu.in_a.ports() + \
    #                              alu.in_b.ports() + \
    #                              alu.out_z.ports())

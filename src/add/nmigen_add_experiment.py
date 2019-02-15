# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Module, Signal, Cat
from nmigen.cli import main, verilog


class FPNum:
    """ Floating-point Number Class, variable-width TODO (currently 32-bit)

        Contains signals for an incoming copy of the value, decoded into
        sign / exponent / mantissa.
        Also contains encoding functions, creation and recognition of
        zero, NaN and inf (all signed)

        Four extra bits are included in the mantissa: the top bit
        (m[-1]) is effectively a carry-overflow.  The other three are
        guard (m[2]), round (m[1]), and sticky (m[0])
    """
    def __init__(self, width, m_width=None):
        self.width = width
        if m_width is None:
            m_width = width - 5 # mantissa extra bits (top,guard,round)
        self.v = Signal(width)      # Latched copy of value
        self.m = Signal(m_width)    # Mantissa
        self.e = Signal((10, True)) # Exponent: 10 bits, signed
        self.s = Signal()           # Sign bit

    def decode(self):
        """ decodes a latched value into sign / exponent / mantissa

            bias is subtracted here, from the exponent.  exponent
            is extended to 10 bits so that subtract 127 is done on
            a 10-bit number
        """
        v = self.v
        return [self.m.eq(Cat(0, 0, 0, v[0:23])),      # mantissa
                self.e.eq(Cat(0,0,0, v[23:31]) - 127), # exponent (minus bias)
                self.s.eq(v[31]),                      # sign
                ]

    def create(self, s, e, m):
        """ creates a value from sign / exponent / mantissa

            bias is added here, to the exponent
        """
        return [
          self.v[31].eq(s),          # sign
          self.v[23:31].eq(e + 127), # exp (add on bias)
          self.v[0:23].eq(m)         # mantissa
        ]

    def shift_down(self):
        """ shifts a mantissa down by one. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)
        """
        return self.create(self.s,
                           self.e + 1,
                           Cat(self.m[0] | self.m[1], self.m[1:-5], 0))

    def nan(self, s):
        return self.create(s, 0x80, 1<<22)

    def inf(self, s):
        return self.create(s, 0x80, 0)

    def zero(self, s):
        return self.create(s, -127, 0)

    def is_nan(self):
        return (self.e == 128) & (self.m != 0)

    def is_inf(self):
        return (self.e == 128) & (self.m == 0)

    def is_zero(self):
        return (self.e == -127) & (self.m == 0)

    def is_overflowed(self):
        return (self.e < 127)

    def is_denormalised(self):
        return (self.e == -126) & (self.m[23] == 0)


class FPADD:
    def __init__(self, width):
        self.width = width

        self.in_a     = Signal(width)
        self.in_a_stb = Signal()
        self.in_a_ack = Signal()

        self.in_b     = Signal(width)
        self.in_b_stb = Signal()
        self.in_b_ack = Signal()

        self.out_z     = Signal(width)
        self.out_z_stb = Signal()
        self.out_z_ack = Signal()

    def get_fragment(self, platform=None):
        m = Module()

        # Latches
        a = FPNum(self.width)
        b = FPNum(self.width)
        z = FPNum(self.width, 24)

        tot = Signal(28)     # sticky/round/guard bits, 23 result, 1 overflow

        guard = Signal()     # tot[2]
        round_bit = Signal() # tot[1]
        sticky = Signal()    # tot[0]

        with m.FSM() as fsm:

            # ******
            # gets operand a

            with m.State("get_a"):
                with m.If((self.in_a_ack) & (self.in_a_stb)):
                    m.next = "get_b"
                    m.d.sync += [
                        a.v.eq(self.in_a),
                        self.in_a_ack.eq(0)
                    ]
                with m.Else():
                    m.d.sync += self.in_a_ack.eq(1)

            # ******
            # gets operand b

            with m.State("get_b"):
                with m.If((self.in_b_ack) & (self.in_b_stb)):
                    m.next = "unpack"
                    m.d.sync += [
                        b.v.eq(self.in_b),
                        self.in_b_ack.eq(0)
                    ]
                with m.Else():
                    m.d.sync += self.in_b_ack.eq(1)

            # ******
            # unpacks operands into sign, mantissa and exponent

            with m.State("unpack"):
                m.next = "special_cases"
                m.d.sync += a.decode()
                m.d.sync += b.decode()

            # ******
            # special cases: NaNs, infs, zeros, denormalised

            with m.State("special_cases"):

                # if a is NaN or b is NaN return NaN
                with m.If(a.is_nan() | b.is_nan()):
                    m.next = "put_z"
                    m.d.sync += z.nan(1)

                # if a is inf return inf (or NaN)
                with m.Elif(a.is_inf()):
                    m.next = "put_z"
                    m.d.sync += z.inf(a.s)
                    # if a is inf and signs don't match return NaN
                    with m.If((b.e == 128) & (a.s != b.s)):
                        m.d.sync += z.nan(b.s)

                # if b is inf return inf
                with m.Elif(b.is_inf()):
                    m.next = "put_z"
                    m.d.sync += z.inf(b.s)

                # if a is zero and b zero return signed-a/b
                with m.Elif(a.is_zero() & b.is_zero()):
                    m.next = "put_z"
                    m.d.sync += z.create(a.s & b.s, b.e[0:8], b.m[3:26])

                # if a is zero return b
                with m.Elif(a.is_zero()):
                    m.next = "put_z"
                    m.d.sync += z.create(b.s, b.e[0:8], b.m[3:26])

                # if b is zero return a
                with m.Elif(b.is_zero()):
                    m.next = "put_z"
                    m.d.sync += z.create(a.s, a.e[0:8], a.m[3:26])

                # Denormalised Number checks
                with m.Else():
                    m.next = "align"
                    # denormalise a check
                    with m.If(a.e == -127):
                        m.d.sync += a.e.eq(-126) # limit a exponent
                    with m.Else():
                        m.d.sync += a.m[26].eq(1) # set top mantissa bit
                    # denormalise b check
                    with m.If(b.e == -127):
                        m.d.sync += b.e.eq(-126) # limit b exponent
                    with m.Else():
                        m.d.sync += b.m[26].eq(1) # set top mantissa bit

            # ******
            # align.  NOTE: this does *not* do single-cycle multi-shifting,
            #         it *STAYS* in the align state until the exponents match

            with m.State("align"):
                # exponent of a greater than b: increment b exp, shift b mant
                with m.If(a.e > b.e):
                    m.d.sync += b.shift_down()
                # exponent of b greater than a: increment a exp, shift a mant
                with m.Elif(a.e < b.e):
                    m.d.sync += a.shift_down()
                # exponents equal: move to next stage.
                with m.Else():
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
                        tot.eq(a.m + b.m),
                        z.s.eq(a.s)
                    ]
                # a mantissa greater than b, use a
                with m.Elif(a.m >= b.m):
                    m.d.sync += [
                        tot.eq(a.m - b.m),
                        z.s.eq(a.s)
                    ]
                # b mantissa greater than a, use b
                with m.Else():
                    m.d.sync += [
                        tot.eq(b.m - a.m),
                        z.s.eq(b.s)
                ]

            # ******
            # Second stage of add: preparation for normalisation.
            # detects when tot sum is too big (tot[27] is kinda a carry bit)

            with m.State("add_1"):
                m.next = "normalise_1"
                # tot[27] gets set when the sum overflows. shift result down
                with m.If(tot[27]):
                    m.d.sync += [
                        z.m.eq(tot[4:28]),
                        guard.eq(tot[3]),
                        round_bit.eq(tot[2]),
                        sticky.eq(tot[1] | tot[0]),
                        z.e.eq(z.e + 1)
                ]
                # tot[27] zero case
                with m.Else():
                    m.d.sync += [
                        z.m.eq(tot[3:27]),
                        guard.eq(tot[2]),
                        round_bit.eq(tot[1]),
                        sticky.eq(tot[0])
                ]

            # ******
            # First stage of normalisation.
            # NOTE: just like "align", this one keeps going round every clock
            #       until the result's exponent is within acceptable "range"
            # NOTE: the weirdness of reassigning guard and round is due to
            #       the extra mantissa bits coming from tot[0..2]

            with m.State("normalise_1"):
                with m.If((z.m[23] == 0) & (z.e > -126)):
                    m.d.sync +=[
                        z.e.eq(z.e - 1),  # DECREASE exponent
                        z.m.eq(z.m << 1), # shift mantissa UP
                        z.m[0].eq(guard), # steal guard bit (was tot[2])
                        guard.eq(round_bit), # steal round_bit (was tot[1])
                    ]
                with m.Else():
                    m.next = "normalize_2"

            # ******
            # Second stage of normalisation.
            # NOTE: just like "align", this one keeps going round every clock
            #       until the result's exponent is within acceptable "range"
            # NOTE: the weirdness of reassigning guard and round is due to
            #       the extra mantissa bits coming from tot[0..2]

            with m.State("normalise_2"):
                with m.If(z.e < -126):
                    m.d.sync +=[
                        z.e.eq(z.e + 1),  # INCREASE exponent
                        z.m.eq(z.m >> 1), # shift mantissa DOWN
                        guard.eq(z.m[0]),
                        round_bit.eq(guard),
                        sticky.eq(sticky | round_bit)
                    ]
                with m.Else():
                    m.next = "round"

            # ******
            # rounding stage

            with m.State("round"):
                m.next = "corrections"
                with m.If(guard & (round_bit | sticky | z.m[0])):
                    m.d.sync += z.m.eq(z.m + 1) # mantissa rounds up
                    with m.If(z.m == 0xffffff): # all 1s
                        m.d.sync += z.e.eq(z.e + 1) # exponent rounds up

            # ******
            # correction stage

            with m.State("corrections"):
                m.next = "pack"
                # denormalised, correct exponent to zero
                with m.If(z.is_denormalised()):
                    m.d.sync += z.m.eq(-127)
                # FIX SIGN BUG: -a + a = +0.
                with m.If((z.e == -126) & (z.m[0:23] == 0)):
                    m.d.sync += z.s.eq(0)

            # ******
            # pack stage

            with m.State("pack"):
                m.next = "put_z"
                # if overflow occurs, return inf
                with m.If(z.is_overflowed()):
                    m.d.sync += z.inf(0)
                with m.Else():
                    m.d.sync += z.create(z.s, z.e, z.m)

            # ******
            # put_z stage

            with m.State("put_z"):
              m.d.sync += [
                  self.out_z_stb.eq(1),
                  self.out_z.eq(z.v)
              ]
              with m.If(self.out_z_stb & self.out_z_ack):
                  m.d.sync += self.out_z_stb.eq(0)
                  m.next = "get_a"

        return m


if __name__ == "__main__":
    alu = FPADD(width=32)
    main(alu, ports=[
                    alu.in_a, alu.in_a_stb, alu.in_a_ack,
                    alu.in_b, alu.in_b_stb, alu.in_b_ack,
                    alu.out_z, alu.out_z_stb, alu.out_z_ack,
        ])


    # works... but don't use, just do "python fname.py convert -t v"
    #print (verilog.convert(alu, ports=[
    #                alu.in_a, alu.in_a_stb, alu.in_a_ack,
    #                alu.in_b, alu.in_b_stb, alu.in_b_ack,
    #                alu.out_z, alu.out_z_stb, alu.out_z_ack,
    #    ]))

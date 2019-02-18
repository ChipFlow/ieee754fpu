# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Signal, Cat, Const, Mux, Module
from math import log
from operator import or_
from functools import reduce

class MultiShiftR:

    def __init__(self, width):
        self.width = width
        self.smax = int(log(width) / log(2))
        self.i = Signal(width)
        self.s = Signal(self.smax)
        self.o = Signal(width)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.i >> self.s)
        return m


class MultiShift:
    """ Generates variable-length single-cycle shifter from a series
        of conditional tests on each bit of the left/right shift operand.
        Each bit tested produces output shifted by that number of bits,
        in a binary fashion: bit 1 if set shifts by 1 bit, bit 2 if set
        shifts by 2 bits, each partial result cascading to the next Mux.

        Could be adapted to do arithmetic shift by taking copies of the
        MSB instead of zeros.
    """

    def __init__(self, width):
        self.width = width
        self.smax = int(log(width) / log(2))

    def lshift(self, op, s):
        res = op << s
        return res[:len(op)]
        res = op
        for i in range(self.smax):
            zeros = [0] * (1<<i)
            res = Mux(s & (1<<i), Cat(zeros, res[0:-(1<<i)]), res)
        return res

    def rshift(self, op, s):
        res = op >> s
        return res[:len(op)]
        res = op
        for i in range(self.smax):
            zeros = [0] * (1<<i)
            res = Mux(s & (1<<i), Cat(res[(1<<i):], zeros), res)
        return res


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
    def __init__(self, width, m_extra=True):
        self.width = width
        m_width = {32: 24, 64: 53}[width]
        e_width = {32: 10, 64: 13}[width]
        e_max = 1<<(e_width-3)
        self.rmw = m_width # real mantissa width (not including extras)
        self.e_max = e_max
        if m_extra:
            # mantissa extra bits (top,guard,round)
            self.m_extra = 3
            m_width += self.m_extra
        else:
            self.m_extra = 0
        #print (m_width, e_width, e_max, self.rmw, self.m_extra)
        self.m_width = m_width
        self.e_width = e_width
        self.e_start = self.rmw - 1
        self.e_end = self.rmw + self.e_width - 3 # for decoding

        self.v = Signal(width)      # Latched copy of value
        self.m = Signal(m_width)    # Mantissa
        self.e = Signal((e_width, True)) # Exponent: 10 bits, signed
        self.s = Signal()           # Sign bit

        self.mzero = Const(0, (m_width, False))
        self.m1s = Const(-1, (m_width, False))
        self.P128 = Const(e_max, (e_width, True))
        self.P127 = Const(e_max-1, (e_width, True))
        self.N127 = Const(-(e_max-1), (e_width, True))
        self.N126 = Const(-(e_max-2), (e_width, True))

    def decode(self, v):
        """ decodes a latched value into sign / exponent / mantissa

            bias is subtracted here, from the exponent.  exponent
            is extended to 10 bits so that subtract 127 is done on
            a 10-bit number
        """
        args = [0] * self.m_extra + [v[0:self.e_start]] # pad with extra zeros
        #print ("decode", self.e_end)
        return [self.m.eq(Cat(*args)), # mantissa
                self.e.eq(v[self.e_start:self.e_end] - self.P127), # exp
                self.s.eq(v[-1]),                 # sign
                ]

    def create(self, s, e, m):
        """ creates a value from sign / exponent / mantissa

            bias is added here, to the exponent
        """
        return [
          self.v[-1].eq(s),          # sign
          self.v[self.e_start:self.e_end].eq(e + self.P127), # exp (add on bias)
          self.v[0:self.e_start].eq(m)         # mantissa
        ]

    def shift_down(self):
        """ shifts a mantissa down by one. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)
        """
        return [self.e.eq(self.e + 1),
                self.m.eq(Cat(self.m[0] | self.m[1], self.m[2:], 0))
               ]

    def shift_down_multi(self, diff):
        """ shifts a mantissa down. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)

            this code works by variable-shifting the mantissa by up to
            its maximum bit-length: no point doing more (it'll still be
            zero).

            the sticky bit is computed by shifting a batch of 1s by
            the same amount, which will introduce zeros.  it's then
            inverted and used as a mask to get the LSBs of the mantissa.
            those are then |'d into the sticky bit.
        """
        sm = MultiShift(self.width)
        mw = Const(self.m_width-1, len(diff))
        maxslen = Mux(diff > mw, mw, diff)
        rs = sm.rshift(self.m[1:], maxslen)
        maxsleni = mw - maxslen
        m_mask = sm.rshift(self.m1s[1:], maxsleni) # shift and invert

        stickybits = reduce(or_, self.m[1:] & m_mask) | self.m[0]
        return [self.e.eq(self.e + diff),
                self.m.eq(Cat(stickybits, rs))
               ]

    def nan(self, s):
        return self.create(s, self.P128, 1<<(self.e_start-1))

    def inf(self, s):
        return self.create(s, self.P128, 0)

    def zero(self, s):
        return self.create(s, self.N127, 0)

    def is_nan(self):
        return (self.e == self.P128) & (self.m != 0)

    def is_inf(self):
        return (self.e == self.P128) & (self.m == 0)

    def is_zero(self):
        return (self.e == self.N127) & (self.m == self.mzero)

    def is_overflowed(self):
        return (self.e > self.P127)

    def is_denormalised(self):
        return (self.e == self.N126) & (self.m[self.e_start] == 0)


class FPOp:
    def __init__(self, width):
        self.width = width

        self.v   = Signal(width)
        self.stb = Signal()
        self.ack = Signal()

    def ports(self):
        return [self.v, self.stb, self.ack]


class Overflow:
    def __init__(self):
        self.guard = Signal()     # tot[2]
        self.round_bit = Signal() # tot[1]
        self.sticky = Signal()    # tot[0]


class FPBase:
    """ IEEE754 Floating Point Base Class

        contains common functions for FP manipulation, such as
        extracting and packing operands, normalisation, denormalisation,
        rounding etc.
    """

    def get_op(self, m, op, v, next_state):
        """ this function moves to the next state and copies the operand
            when both stb and ack are 1.
            acknowledgement is sent by setting ack to ZERO.
        """
        with m.If((op.ack) & (op.stb)):
            m.next = next_state
            m.d.sync += [
                v.decode(op.v),
                op.ack.eq(0)
            ]
        with m.Else():
            m.d.sync += op.ack.eq(1)

    def denormalise(self, m, a):
        """ denormalises a number.  this is probably the wrong name for
            this function.  for normalised numbers (exponent != minimum)
            one *extra* bit (the implicit 1) is added *back in*.
            for denormalised numbers, the mantissa is left alone
            and the exponent increased by 1.

            both cases *effectively multiply the number stored by 2*,
            which has to be taken into account when extracting the result.
        """
        with m.If(a.e == a.N127):
            m.d.sync += a.e.eq(a.N126) # limit a exponent
        with m.Else():
            m.d.sync += a.m[-1].eq(1) # set top mantissa bit

    def op_normalise(self, m, op, next_state):
        """ operand normalisation
            NOTE: just like "align", this one keeps going round every clock
                  until the result's exponent is within acceptable "range"
        """
        with m.If((op.m[-1] == 0)): # check last bit of mantissa
            m.d.sync +=[
                op.e.eq(op.e - 1),  # DECREASE exponent
                op.m.eq(op.m << 1), # shift mantissa UP
            ]
        with m.Else():
            m.next = next_state

    def normalise_1(self, m, z, of, next_state):
        """ first stage normalisation

            NOTE: just like "align", this one keeps going round every clock
                  until the result's exponent is within acceptable "range"
            NOTE: the weirdness of reassigning guard and round is due to
                  the extra mantissa bits coming from tot[0..2]
        """
        with m.If((z.m[-1] == 0) & (z.e > z.N126)):
            m.d.sync +=[
                z.e.eq(z.e - 1),  # DECREASE exponent
                z.m.eq(z.m << 1), # shift mantissa UP
                z.m[0].eq(of.guard),       # steal guard bit (was tot[2])
                of.guard.eq(of.round_bit), # steal round_bit (was tot[1])
                of.round_bit.eq(0),        # reset round bit
            ]
        with m.Else():
            m.next = next_state

    def normalise_2(self, m, z, of, next_state):
        """ second stage normalisation

            NOTE: just like "align", this one keeps going round every clock
                  until the result's exponent is within acceptable "range"
            NOTE: the weirdness of reassigning guard and round is due to
                  the extra mantissa bits coming from tot[0..2]
        """
        with m.If(z.e < z.N126):
            m.d.sync +=[
                z.e.eq(z.e + 1),  # INCREASE exponent
                z.m.eq(z.m >> 1), # shift mantissa DOWN
                of.guard.eq(z.m[0]),
                of.round_bit.eq(of.guard),
                of.sticky.eq(of.sticky | of.round_bit)
            ]
        with m.Else():
            m.next = next_state

    def roundz(self, m, z, of, next_state):
        """ performs rounding on the output.  TODO: different kinds of rounding
        """
        m.next = next_state
        with m.If(of.guard & (of.round_bit | of.sticky | z.m[0])):
            m.d.sync += z.m.eq(z.m + 1) # mantissa rounds up
            with m.If(z.m == z.m1s): # all 1s
                m.d.sync += z.e.eq(z.e + 1) # exponent rounds up

    def corrections(self, m, z, next_state):
        """ denormalisation and sign-bug corrections
        """
        m.next = next_state
        # denormalised, correct exponent to zero
        with m.If(z.is_denormalised()):
            m.d.sync += z.e.eq(z.N127)
        # FIX SIGN BUG: -a + a = +0.
        with m.If((z.e == z.N126) & (z.m[0:] == 0)):
            m.d.sync += z.s.eq(0)

    def pack(self, m, z, next_state):
        """ packs the result into the output (detects overflow->Inf)
        """
        m.next = next_state
        # if overflow occurs, return inf
        with m.If(z.is_overflowed()):
            m.d.sync += z.inf(0)
        with m.Else():
            m.d.sync += z.create(z.s, z.e, z.m)

    def put_z(self, m, z, out_z, next_state):
        """ put_z: stores the result in the output.  raises stb and waits
            for ack to be set to 1 before moving to the next state.
            resets stb back to zero when that occurs, as acknowledgement.
        """
        m.d.sync += [
          out_z.stb.eq(1),
          out_z.v.eq(z.v)
        ]
        with m.If(out_z.stb & out_z.ack):
            m.d.sync += out_z.stb.eq(0)
            m.next = next_state



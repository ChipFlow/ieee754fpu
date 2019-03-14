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
        self.i = Signal(width, reset_less=True)
        self.s = Signal(self.smax, reset_less=True)
        self.o = Signal(width, reset_less=True)

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


class FPNumBase:
    """ Floating-point Base Number Class
    """
    def __init__(self, width, m_extra=True):
        self.width = width
        m_width = {16: 11, 32: 24, 64: 53}[width] # 1 extra bit (overflow)
        e_width = {16: 7,  32: 10, 64: 13}[width] # 2 extra bits (overflow)
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

        self.v = Signal(width, reset_less=True)      # Latched copy of value
        self.m = Signal(m_width, reset_less=True)    # Mantissa
        self.e = Signal((e_width, True), reset_less=True) # Exponent: IEEE754exp+2 bits, signed
        self.s = Signal(reset_less=True)           # Sign bit

        self.mzero = Const(0, (m_width, False))
        self.m1s = Const(-1, (m_width, False))
        self.P128 = Const(e_max, (e_width, True))
        self.P127 = Const(e_max-1, (e_width, True))
        self.N127 = Const(-(e_max-1), (e_width, True))
        self.N126 = Const(-(e_max-2), (e_width, True))

        self.is_nan = Signal(reset_less=True)
        self.is_zero = Signal(reset_less=True)
        self.is_inf = Signal(reset_less=True)
        self.is_overflowed = Signal(reset_less=True)
        self.is_denormalised = Signal(reset_less=True)
        self.exp_128 = Signal(reset_less=True)
        self.exp_sub_n126 = Signal((e_width, True), reset_less=True)
        self.exp_lt_n126 = Signal(reset_less=True)
        self.exp_gt_n126 = Signal(reset_less=True)
        self.exp_gt127 = Signal(reset_less=True)
        self.exp_n127 = Signal(reset_less=True)
        self.exp_n126 = Signal(reset_less=True)
        self.m_zero = Signal(reset_less=True)
        self.m_msbzero = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.is_nan.eq(self._is_nan())
        m.d.comb += self.is_zero.eq(self._is_zero())
        m.d.comb += self.is_inf.eq(self._is_inf())
        m.d.comb += self.is_overflowed.eq(self._is_overflowed())
        m.d.comb += self.is_denormalised.eq(self._is_denormalised())
        m.d.comb += self.exp_128.eq(self.e == self.P128)
        m.d.comb += self.exp_sub_n126.eq(self.e - self.N126)
        m.d.comb += self.exp_gt_n126.eq(self.exp_sub_n126 > 0)
        m.d.comb += self.exp_lt_n126.eq(self.exp_sub_n126 < 0)
        m.d.comb += self.exp_gt127.eq(self.e > self.P127)
        m.d.comb += self.exp_n127.eq(self.e == self.N127)
        m.d.comb += self.exp_n126.eq(self.e == self.N126)
        m.d.comb += self.m_zero.eq(self.m == self.mzero)
        m.d.comb += self.m_msbzero.eq(self.m[self.e_start] == 0)

        return m

    def _is_nan(self):
        return (self.exp_128) & (~self.m_zero)

    def _is_inf(self):
        return (self.exp_128) & (self.m_zero)

    def _is_zero(self):
        return (self.exp_n127) & (self.m_zero)

    def _is_overflowed(self):
        return self.exp_gt127

    def _is_denormalised(self):
        return (self.exp_n126) & (self.m_msbzero)

    def copy(self, inp):
        return [self.s.eq(inp.s), self.e.eq(inp.e), self.m.eq(inp.m)]


class FPNumOut(FPNumBase):
    """ Floating-point Number Class

        Contains signals for an incoming copy of the value, decoded into
        sign / exponent / mantissa.
        Also contains encoding functions, creation and recognition of
        zero, NaN and inf (all signed)

        Four extra bits are included in the mantissa: the top bit
        (m[-1]) is effectively a carry-overflow.  The other three are
        guard (m[2]), round (m[1]), and sticky (m[0])
    """
    def __init__(self, width, m_extra=True):
        FPNumBase.__init__(self, width, m_extra)

    def elaborate(self, platform):
        m = FPNumBase.elaborate(self, platform)

        return m

    def create(self, s, e, m):
        """ creates a value from sign / exponent / mantissa

            bias is added here, to the exponent
        """
        return [
          self.v[-1].eq(s),          # sign
          self.v[self.e_start:self.e_end].eq(e + self.P127), # exp (add on bias)
          self.v[0:self.e_start].eq(m)         # mantissa
        ]

    def nan(self, s):
        return self.create(s, self.P128, 1<<(self.e_start-1))

    def inf(self, s):
        return self.create(s, self.P128, 0)

    def zero(self, s):
        return self.create(s, self.N127, 0)


class MultiShiftRMerge:
    """ shifts down (right) and merges lower bits into m[0].
        m[0] is the "sticky" bit, basically
    """
    def __init__(self, width, s_max=None):
        if s_max is None:
            s_max = int(log(width) / log(2))
        self.smax = s_max
        self.m = Signal(width, reset_less=True)
        self.inp = Signal(width, reset_less=True)
        self.diff = Signal(s_max, reset_less=True)
        self.width = width

    def elaborate(self, platform):
        m = Module()

        rs = Signal(self.width, reset_less=True)
        m_mask = Signal(self.width, reset_less=True)
        smask = Signal(self.width, reset_less=True)
        stickybit = Signal(reset_less=True)
        maxslen = Signal(self.smax, reset_less=True)
        maxsleni = Signal(self.smax, reset_less=True)

        sm = MultiShift(self.width-1)
        m0s = Const(0, self.width-1)
        mw = Const(self.width-1, len(self.diff))
        m.d.comb += [maxslen.eq(Mux(self.diff > mw, mw, self.diff)),
                     maxsleni.eq(Mux(self.diff > mw, 0, mw-self.diff)),
                    ]

        m.d.comb += [
                # shift mantissa by maxslen, mask by inverse
                rs.eq(sm.rshift(self.inp[1:], maxslen)),
                m_mask.eq(sm.rshift(~m0s, maxsleni)),
                smask.eq(self.inp[1:] & m_mask),
                # sticky bit combines all mask (and mantissa low bit)
                stickybit.eq(smask.bool() | self.inp[0]),
                # mantissa result contains m[0] already.
                self.m.eq(Cat(stickybit, rs))
           ]
        return m


class FPNumShift(FPNumBase):
    """ Floating-point Number Class for shifting
    """
    def __init__(self, mainm, op, inv, width, m_extra=True):
        FPNumBase.__init__(self, width, m_extra)
        self.latch_in = Signal()
        self.mainm = mainm
        self.inv = inv
        self.op = op

    def elaborate(self, platform):
        m = FPNumBase.elaborate(self, platform)

        m.d.comb += self.s.eq(op.s)
        m.d.comb += self.e.eq(op.e)
        m.d.comb += self.m.eq(op.m)

        with self.mainm.State("align"):
            with m.If(self.e < self.inv.e):
                m.d.sync += self.shift_down()

        return m

    def shift_down(self, inp):
        """ shifts a mantissa down by one. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)
        """
        return [self.e.eq(inp.e + 1),
                self.m.eq(Cat(inp.m[0] | inp.m[1], inp.m[2:], 0))
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

    def shift_up_multi(self, diff):
        """ shifts a mantissa up. exponent is decreased to compensate
        """
        sm = MultiShift(self.width)
        mw = Const(self.m_width, len(diff))
        maxslen = Mux(diff > mw, mw, diff)

        return [self.e.eq(self.e - diff),
                self.m.eq(sm.lshift(self.m, maxslen))
               ]

class FPNumIn(FPNumBase):
    """ Floating-point Number Class

        Contains signals for an incoming copy of the value, decoded into
        sign / exponent / mantissa.
        Also contains encoding functions, creation and recognition of
        zero, NaN and inf (all signed)

        Four extra bits are included in the mantissa: the top bit
        (m[-1]) is effectively a carry-overflow.  The other three are
        guard (m[2]), round (m[1]), and sticky (m[0])
    """
    def __init__(self, op, width, m_extra=True):
        FPNumBase.__init__(self, width, m_extra)
        self.latch_in = Signal()
        self.op = op

    def elaborate(self, platform):
        m = FPNumBase.elaborate(self, platform)

        #m.d.comb += self.latch_in.eq(self.op.ack & self.op.stb)
        #with m.If(self.latch_in):
        #    m.d.sync += self.decode(self.v)

        return m

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

    def shift_down(self, inp):
        """ shifts a mantissa down by one. exponent is increased to compensate

            accuracy is lost as a result in the mantissa however there are 3
            guard bits (the latter of which is the "sticky" bit)
        """
        return [self.e.eq(inp.e + 1),
                self.m.eq(Cat(inp.m[0] | inp.m[1], inp.m[2:], 0))
               ]

    def shift_down_multi(self, diff, inp=None):
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
        if inp is None:
            inp = self
        sm = MultiShift(self.width)
        mw = Const(self.m_width-1, len(diff))
        maxslen = Mux(diff > mw, mw, diff)
        rs = sm.rshift(inp.m[1:], maxslen)
        maxsleni = mw - maxslen
        m_mask = sm.rshift(self.m1s[1:], maxsleni) # shift and invert

        #stickybit = reduce(or_, inp.m[1:] & m_mask) | inp.m[0]
        stickybit = (inp.m[1:] & m_mask).bool() | inp.m[0]
        return [self.e.eq(inp.e + diff),
                self.m.eq(Cat(stickybit, rs))
               ]

    def shift_up_multi(self, diff):
        """ shifts a mantissa up. exponent is decreased to compensate
        """
        sm = MultiShift(self.width)
        mw = Const(self.m_width, len(diff))
        maxslen = Mux(diff > mw, mw, diff)

        return [self.e.eq(self.e - diff),
                self.m.eq(sm.lshift(self.m, maxslen))
               ]

class Trigger:
    def __init__(self):

        self.stb = Signal(reset=0)
        self.ack = Signal()
        self.trigger = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.stb & self.ack)
        return m

    def copy(self, inp):
        return [self.stb.eq(inp.stb),
                self.ack.eq(inp.ack)
               ]

    def ports(self):
        return [self.stb, self.ack]


class FPOp(Trigger):
    def __init__(self, width):
        Trigger.__init__(self)
        self.width = width

        self.v   = Signal(width)

    def chain_inv(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(~self.ack), # send ACK
               ]

    def chain_from(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(self.ack), # send ACK
               ]

    def copy(self, inp):
        return [self.v.eq(inp.v),
                self.stb.eq(inp.stb),
                self.ack.eq(inp.ack)
               ]

    def ports(self):
        return [self.v, self.stb, self.ack]


class Overflow:
    def __init__(self):
        self.guard = Signal(reset_less=True)     # tot[2]
        self.round_bit = Signal(reset_less=True) # tot[1]
        self.sticky = Signal(reset_less=True)    # tot[0]
        self.m0 = Signal(reset_less=True)        # mantissa zero bit

        self.roundz = Signal(reset_less=True)

    def copy(self, inp):
        return [self.guard.eq(inp.guard),
                self.round_bit.eq(inp.round_bit),
                self.sticky.eq(inp.sticky),
                self.m0.eq(inp.m0)]

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.roundz.eq(self.guard & \
                                   (self.round_bit | self.sticky | self.m0))
        return m


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
                # op is latched in from FPNumIn class on same ack/stb
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
        with m.If(a.exp_n127):
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
            m.d.sync += [
                z.e.eq(z.e - 1),  # DECREASE exponent
                z.m.eq(z.m << 1), # shift mantissa UP
                z.m[0].eq(of.guard),       # steal guard bit (was tot[2])
                of.guard.eq(of.round_bit), # steal round_bit (was tot[1])
                of.round_bit.eq(0),        # reset round bit
                of.m0.eq(of.guard),
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
                of.m0.eq(z.m[1]),
                of.round_bit.eq(of.guard),
                of.sticky.eq(of.sticky | of.round_bit)
            ]
        with m.Else():
            m.next = next_state

    def roundz(self, m, z, of):
        """ performs rounding on the output.  TODO: different kinds of rounding
        """
        with m.If(of.guard & (of.round_bit | of.sticky | z.m[0])):
            m.d.sync += z.m.eq(z.m + 1) # mantissa rounds up
            with m.If(z.m == z.m1s): # all 1s
                m.d.sync += z.e.eq(z.e + 1) # exponent rounds up

    def corrections(self, m, z, next_state):
        """ denormalisation and sign-bug corrections
        """
        m.next = next_state
        # denormalised, correct exponent to zero
        with m.If(z.is_denormalised):
            m.d.sync += z.e.eq(z.N127)

    def pack(self, m, z, next_state):
        """ packs the result into the output (detects overflow->Inf)
        """
        m.next = next_state
        # if overflow occurs, return inf
        with m.If(z.is_overflowed):
            m.d.sync += z.inf(z.s)
        with m.Else():
            m.d.sync += z.create(z.s, z.e, z.m)

    def put_z(self, m, z, out_z, next_state):
        """ put_z: stores the result in the output.  raises stb and waits
            for ack to be set to 1 before moving to the next state.
            resets stb back to zero when that occurs, as acknowledgement.
        """
        m.d.sync += [
          out_z.v.eq(z.v)
        ]
        with m.If(out_z.stb & out_z.ack):
            m.d.sync += out_z.stb.eq(0)
            m.next = next_state
        with m.Else():
            m.d.sync += out_z.stb.eq(1)



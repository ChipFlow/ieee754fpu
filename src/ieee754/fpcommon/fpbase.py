# IEEE Floating Point Adder (Single Precision)
# Copyright (C) Jonathan P Dawson 2013
# 2013-12-12

from nmigen import Signal, Cat, Const, Mux, Module, Elaboratable
from math import log
from operator import or_
from functools import reduce

from nmutil.singlepipe import PrevControl, NextControl
from nmutil.pipeline import ObjectProxy
import unittest
import math


class FPFormat:
    """ Class describing binary floating-point formats based on IEEE 754.

    :attribute e_width: the number of bits in the exponent field.
    :attribute m_width: the number of bits stored in the mantissa
        field.
    :attribute has_int_bit: if the FP format has an explicit integer bit (like
        the x87 80-bit format). The bit is considered part of the mantissa.
    :attribute has_sign: if the FP format has a sign bit. (Some Vulkan
        Image/Buffer formats are FP numbers without a sign bit.)
    """

    def __init__(self,
                 e_width,
                 m_width,
                 has_int_bit=False,
                 has_sign=True):
        """ Create ``FPFormat`` instance. """
        self.e_width = e_width
        self.m_width = m_width
        self.has_int_bit = has_int_bit
        self.has_sign = has_sign

    def __eq__(self, other):
        """ Check for equality. """
        if not isinstance(other, FPFormat):
            return NotImplemented
        return (self.e_width == other.e_width and
                self.m_width == other.m_width and
                self.has_int_bit == other.has_int_bit and
                self.has_sign == other.has_sign)

    @staticmethod
    def standard(width):
        """ Get standard IEEE 754-2008 format.

        :param width: bit-width of requested format.
        :returns: the requested ``FPFormat`` instance.
        """
        if width == 16:
            return FPFormat(5, 10)
        if width == 32:
            return FPFormat(8, 23)
        if width == 64:
            return FPFormat(11, 52)
        if width == 128:
            return FPFormat(15, 112)
        if width > 128 and width % 32 == 0:
            if width > 1000000:  # arbitrary upper limit
                raise ValueError("width too big")
            e_width = round(4 * math.log2(width)) - 13
            return FPFormat(e_width, width - 1 - e_width)
        raise ValueError("width must be the bit-width of a valid IEEE"
                         " 754-2008 binary format")

    def __repr__(self):
        """ Get repr. """
        try:
            if self == self.standard(self.width):
                return f"FPFormat.standard({self.width})"
        except ValueError:
            pass
        retval = f"FPFormat({self.e_width}, {self.m_width}"
        if self.has_int_bit is not False:
            retval += f", {self.has_int_bit}"
        if self.has_sign is not True:
            retval += f", {self.has_sign}"
        return retval + ")"

    def get_sign(self, x):
        """ returns the sign of its input number, x (assumes number is signed)
        """
        return x >> (self.e_width + self.m_width)

    def get_exponent(self, x):
        """ returns the exponent of its input number, x
        """
        x = ((x >> self.m_width) & self.exponent_inf_nan)
        return x - self.exponent_bias

    def get_mantissa(self, x):
        """ returns the mantissa of its input number, x
        """
        return x & self.mantissa_mask

    def is_zero(self, x):
        """ returns true if x is subnormal (exp at minimum
        """
        e_sub = self.exponent_denormal_zero - self.exponent_bias
        return self.get_exponent(x) == e_sub and self.get_mantissa(x) == 0

    def is_subnormal(self, x):
        """ returns true if x is subnormal (exp at minimum
        """
        e_sub = self.exponent_denormal_zero - self.exponent_bias
        return self.get_exponent(x) == e_sub and self.get_mantissa(x) != 0

    def is_inf(self, x):
        """ returns true if x is infinite
        """
        return (self.get_exponent(x) == self.emax and
                self.get_mantissa(x) == 0)

    def is_nan(self, x):
        """ returns true if x is nan
        """
        highbit = 1<<(self.m_width-1)
        return (self.get_exponent(x) == self.emax and
                self.get_mantissa(x) != 0 and
                self.get_mantissa(x) & highbit != 0)

    def is_nan_signalling(self, x):
        """ returns true if x is a signalling nan
        """
        highbit = 1<<(self.m_width-1)
        print ("m", self.get_mantissa(x), self.get_mantissa(x) != 0,
                self.get_mantissa(x) & highbit)

        return ((self.get_exponent(x) == self.emax) and
                (self.get_mantissa(x) != 0) and
                (self.get_mantissa(x) & highbit) == 0)

    @property
    def width(self):
        """ Get the total number of bits in the FP format. """
        return self.has_sign + self.e_width + self.m_width

    @property
    def mantissa_mask(self):
        """ Get the value of the exponent field designating infinity/NaN. """
        return (1 << self.m_width) - 1

    @property
    def exponent_inf_nan(self):
        """ Get the value of the exponent field designating infinity/NaN. """
        return (1 << self.e_width) - 1

    @property
    def emax(self):
        """ get the maximum exponent (minus bias)
        """
        return self.exponent_inf_nan - self.exponent_bias

    @property
    def exponent_denormal_zero(self):
        """ Get the value of the exponent field designating denormal/zero. """
        return 0

    @property
    def exponent_min_normal(self):
        """ Get the minimum value of the exponent field for normal numbers. """
        return 1

    @property
    def exponent_max_normal(self):
        """ Get the maximum value of the exponent field for normal numbers. """
        return self.exponent_inf_nan - 1

    @property
    def exponent_bias(self):
        """ Get the exponent bias. """
        return (1 << (self.e_width - 1)) - 1

    @property
    def fraction_width(self):
        """ Get the number of mantissa bits that are fraction bits. """
        return self.m_width - self.has_int_bit


class TestFPFormat(unittest.TestCase):
    """ very quick test for FPFormat
    """

    def test_fpformat_fp64(self):
        f64 = FPFormat.standard(64)
        from sfpy import Float64
        x = Float64(1.0).bits
        print (hex(x))

        self.assertEqual(f64.get_exponent(x), 0)
        x = Float64(2.0).bits
        print (hex(x))
        self.assertEqual(f64.get_exponent(x), 1)

        x = Float64(1.5).bits
        m = f64.get_mantissa(x)
        print (hex(x), hex(m))
        self.assertEqual(m, 0x8000000000000)

        s = f64.get_sign(x)
        print (hex(x), hex(s))
        self.assertEqual(s, 0)

        x = Float64(-1.5).bits
        s = f64.get_sign(x)
        print (hex(x), hex(s))
        self.assertEqual(s, 1)

    def test_fpformat_fp32(self):
        f32 = FPFormat.standard(32)
        from sfpy import Float32
        x = Float32(1.0).bits
        print (hex(x))

        self.assertEqual(f32.get_exponent(x), 0)
        x = Float32(2.0).bits
        print (hex(x))
        self.assertEqual(f32.get_exponent(x), 1)

        x = Float32(1.5).bits
        m = f32.get_mantissa(x)
        print (hex(x), hex(m))
        self.assertEqual(m, 0x400000)

        # NaN test
        x = Float32(-1.0).sqrt()
        x = x.bits
        i = f32.is_nan(x)
        print (hex(x), "nan", f32.get_exponent(x), f32.emax,
               f32.get_mantissa(x), i)
        self.assertEqual(i, True)

        # Inf test
        x = Float32(1e36) * Float32(1e36) * Float32(1e36)
        x = x.bits
        i = f32.is_inf(x)
        print (hex(x), "inf", f32.get_exponent(x), f32.emax,
               f32.get_mantissa(x), i)
        self.assertEqual(i, True)

        # subnormal
        x = Float32(1e-41)
        x = x.bits
        i = f32.is_subnormal(x)
        print (hex(x), "sub", f32.get_exponent(x), f32.emax,
               f32.get_mantissa(x), i)
        self.assertEqual(i, True)

        x = Float32(0.0)
        x = x.bits
        i = f32.is_subnormal(x)
        print (hex(x), "sub", f32.get_exponent(x), f32.emax,
               f32.get_mantissa(x), i)
        self.assertEqual(i, False)

        # zero
        i = f32.is_zero(x)
        print (hex(x), "zero", f32.get_exponent(x), f32.emax,
               f32.get_mantissa(x), i)
        self.assertEqual(i, True)

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

    def rshift(self, op, s):
        res = op >> s
        return res[:len(op)]


class FPNumBaseRecord:
    """ Floating-point Base Number Class
    """

    def __init__(self, width, m_extra=True, e_extra=False):
        self.width = width
        m_width = {16: 11, 32: 24, 64: 53}[width]  # 1 extra bit (overflow)
        e_width = {16: 7,  32: 10, 64: 13}[width]  # 2 extra bits (overflow)
        e_max = 1 << (e_width-3)
        self.rmw = m_width - 1  # real mantissa width (not including extras)
        self.e_max = e_max
        if m_extra:
            # mantissa extra bits (top,guard,round)
            self.m_extra = 3
            m_width += self.m_extra
        else:
            self.m_extra = 0
        if e_extra:
            self.e_extra = 6  # enough to cover FP64 when converting to FP16
            e_width += self.e_extra
        else:
            self.e_extra = 0
        # print (m_width, e_width, e_max, self.rmw, self.m_extra)
        self.m_width = m_width
        self.e_width = e_width
        self.e_start = self.rmw
        self.e_end = self.rmw + self.e_width - 2  # for decoding

        self.v = Signal(width, reset_less=True)      # Latched copy of value
        self.m = Signal(m_width, reset_less=True)    # Mantissa
        self.e = Signal((e_width, True), reset_less=True)  # exp+2 bits, signed
        self.s = Signal(reset_less=True)           # Sign bit

        self.fp = self
        self.drop_in(self)

    def drop_in(self, fp):
        fp.s = self.s
        fp.e = self.e
        fp.m = self.m
        fp.v = self.v
        fp.rmw = self.rmw
        fp.width = self.width
        fp.e_width = self.e_width
        fp.e_max = self.e_max
        fp.m_width = self.m_width
        fp.e_start = self.e_start
        fp.e_end = self.e_end
        fp.m_extra = self.m_extra

        m_width = self.m_width
        e_max = self.e_max
        e_width = self.e_width

        self.mzero = Const(0, (m_width, False))
        m_msb = 1 << (self.m_width-2)
        self.msb1 = Const(m_msb, (m_width, False))
        self.m1s = Const(-1, (m_width, False))
        self.P128 = Const(e_max, (e_width, True))
        self.P127 = Const(e_max-1, (e_width, True))
        self.N127 = Const(-(e_max-1), (e_width, True))
        self.N126 = Const(-(e_max-2), (e_width, True))

    def create(self, s, e, m):
        """ creates a value from sign / exponent / mantissa

            bias is added here, to the exponent.

            NOTE: order is important, because e_start/e_end can be
            a bit too long (overwriting s).
        """
        return [
          self.v[0:self.e_start].eq(m),        # mantissa
          self.v[self.e_start:self.e_end].eq(e + self.fp.P127),  # (add bias)
          self.v[-1].eq(s),          # sign
        ]

    def _nan(self, s):
        return (s, self.fp.P128, 1 << (self.e_start-1))

    def _inf(self, s):
        return (s, self.fp.P128, 0)

    def _zero(self, s):
        return (s, self.fp.N127, 0)

    def nan(self, s):
        return self.create(*self._nan(s))

    def inf(self, s):
        return self.create(*self._inf(s))

    def zero(self, s):
        return self.create(*self._zero(s))

    def create2(self, s, e, m):
        """ creates a value from sign / exponent / mantissa

            bias is added here, to the exponent
        """
        e = e + self.P127  # exp (add on bias)
        return Cat(m[0:self.e_start],
                   e[0:self.e_end-self.e_start],
                   s)

    def nan2(self, s):
        return self.create2(s, self.P128, self.msb1)

    def inf2(self, s):
        return self.create2(s, self.P128, self.mzero)

    def zero2(self, s):
        return self.create2(s, self.N127, self.mzero)

    def __iter__(self):
        yield self.s
        yield self.e
        yield self.m

    def eq(self, inp):
        return [self.s.eq(inp.s), self.e.eq(inp.e), self.m.eq(inp.m)]


class FPNumBase(FPNumBaseRecord, Elaboratable):
    """ Floating-point Base Number Class
    """

    def __init__(self, fp):
        fp.drop_in(self)
        self.fp = fp
        e_width = fp.e_width

        self.is_nan = Signal(reset_less=True)
        self.is_zero = Signal(reset_less=True)
        self.is_inf = Signal(reset_less=True)
        self.is_overflowed = Signal(reset_less=True)
        self.is_denormalised = Signal(reset_less=True)
        self.exp_128 = Signal(reset_less=True)
        self.exp_sub_n126 = Signal((e_width, True), reset_less=True)
        self.exp_lt_n126 = Signal(reset_less=True)
        self.exp_zero = Signal(reset_less=True)
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
        m.d.comb += self.exp_128.eq(self.e == self.fp.P128)
        m.d.comb += self.exp_sub_n126.eq(self.e - self.fp.N126)
        m.d.comb += self.exp_gt_n126.eq(self.exp_sub_n126 > 0)
        m.d.comb += self.exp_lt_n126.eq(self.exp_sub_n126 < 0)
        m.d.comb += self.exp_zero.eq(self.e == 0)
        m.d.comb += self.exp_gt127.eq(self.e > self.fp.P127)
        m.d.comb += self.exp_n127.eq(self.e == self.fp.N127)
        m.d.comb += self.exp_n126.eq(self.e == self.fp.N126)
        m.d.comb += self.m_zero.eq(self.m == self.fp.mzero)
        m.d.comb += self.m_msbzero.eq(self.m[self.fp.e_start] == 0)

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
        # XXX NOT to be used for "official" quiet NaN tests!
        # particularly when the MSB has been extended
        return (self.exp_n126) & (self.m_msbzero)


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

    def __init__(self, fp):
        FPNumBase.__init__(self, fp)

    def elaborate(self, platform):
        m = FPNumBase.elaborate(self, platform)

        return m


class MultiShiftRMerge(Elaboratable):
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


class FPNumShift(FPNumBase, Elaboratable):
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
        m_mask = sm.rshift(self.m1s[1:], maxsleni)  # shift and invert

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


class FPNumDecode(FPNumBase):
    """ Floating-point Number Class

        Contains signals for an incoming copy of the value, decoded into
        sign / exponent / mantissa.
        Also contains encoding functions, creation and recognition of
        zero, NaN and inf (all signed)

        Four extra bits are included in the mantissa: the top bit
        (m[-1]) is effectively a carry-overflow.  The other three are
        guard (m[2]), round (m[1]), and sticky (m[0])
    """

    def __init__(self, op, fp):
        FPNumBase.__init__(self, fp)
        self.op = op

    def elaborate(self, platform):
        m = FPNumBase.elaborate(self, platform)

        m.d.comb += self.decode(self.v)

        return m

    def decode(self, v):
        """ decodes a latched value into sign / exponent / mantissa

            bias is subtracted here, from the exponent.  exponent
            is extended to 10 bits so that subtract 127 is done on
            a 10-bit number
        """
        args = [0] * self.m_extra + [v[0:self.e_start]]  # pad with extra zeros
        #print ("decode", self.e_end)
        return [self.m.eq(Cat(*args)),  # mantissa
                self.e.eq(v[self.e_start:self.e_end] - self.fp.P127),  # exp
                self.s.eq(v[-1]),                 # sign
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

    def __init__(self, op, fp):
        FPNumBase.__init__(self, fp)
        self.latch_in = Signal()
        self.op = op

    def decode2(self, m):
        """ decodes a latched value into sign / exponent / mantissa

            bias is subtracted here, from the exponent.  exponent
            is extended to 10 bits so that subtract 127 is done on
            a 10-bit number
        """
        v = self.v
        args = [0] * self.m_extra + [v[0:self.e_start]]  # pad with extra zeros
        #print ("decode", self.e_end)
        res = ObjectProxy(m, pipemode=False)
        res.m = Cat(*args)                             # mantissa
        res.e = v[self.e_start:self.e_end] - self.fp.P127  # exp
        res.s = v[-1]                                  # sign
        return res

    def decode(self, v):
        """ decodes a latched value into sign / exponent / mantissa

            bias is subtracted here, from the exponent.  exponent
            is extended to 10 bits so that subtract 127 is done on
            a 10-bit number
        """
        args = [0] * self.m_extra + [v[0:self.e_start]]  # pad with extra zeros
        #print ("decode", self.e_end)
        return [self.m.eq(Cat(*args)),  # mantissa
                self.e.eq(v[self.e_start:self.e_end] - self.P127),  # exp
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
        m_mask = sm.rshift(self.m1s[1:], maxsleni)  # shift and invert

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


class Trigger(Elaboratable):
    def __init__(self):

        self.stb = Signal(reset=0)
        self.ack = Signal()
        self.trigger = Signal(reset_less=True)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.trigger.eq(self.stb & self.ack)
        return m

    def eq(self, inp):
        return [self.stb.eq(inp.stb),
                self.ack.eq(inp.ack)
                ]

    def ports(self):
        return [self.stb, self.ack]


class FPOpIn(PrevControl):
    def __init__(self, width):
        PrevControl.__init__(self)
        self.width = width

    @property
    def v(self):
        return self.data_i

    def chain_inv(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(~self.ack),  # send ACK
                ]

    def chain_from(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(self.ack),  # send ACK
                ]


class FPOpOut(NextControl):
    def __init__(self, width):
        NextControl.__init__(self)
        self.width = width

    @property
    def v(self):
        return self.data_o

    def chain_inv(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(~self.ack),  # send ACK
                ]

    def chain_from(self, in_op, extra=None):
        stb = in_op.stb
        if extra is not None:
            stb = stb & extra
        return [self.v.eq(in_op.v),          # receive value
                self.stb.eq(stb),      # receive STB
                in_op.ack.eq(self.ack),  # send ACK
                ]


class Overflow:  # (Elaboratable):
    def __init__(self, name=None):
        if name is None:
            name = ""
        self.guard = Signal(reset_less=True, name=name+"guard")     # tot[2]
        self.round_bit = Signal(reset_less=True, name=name+"round")  # tot[1]
        self.sticky = Signal(reset_less=True, name=name+"sticky")   # tot[0]
        self.m0 = Signal(reset_less=True, name=name+"m0")  # mantissa bit 0

        #self.roundz = Signal(reset_less=True)

    def __iter__(self):
        yield self.guard
        yield self.round_bit
        yield self.sticky
        yield self.m0

    def eq(self, inp):
        return [self.guard.eq(inp.guard),
                self.round_bit.eq(inp.round_bit),
                self.sticky.eq(inp.sticky),
                self.m0.eq(inp.m0)]

    @property
    def roundz(self):
        return self.guard & (self.round_bit | self.sticky | self.m0)


class OverflowMod(Elaboratable, Overflow):
    def __init__(self, name=None):
        Overflow.__init__(self, name)
        if name is None:
            name = ""
        self.roundz_out = Signal(reset_less=True, name=name+"roundz_out")

    def __iter__(self):
        yield from Overflow.__iter__(self)
        yield self.roundz_out

    def eq(self, inp):
        return [self.roundz_out.eq(inp.roundz_out)] + Overflow.eq(self)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.roundz_out.eq(self.roundz)
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
        res = v.decode2(m)
        ack = Signal()
        with m.If((op.ready_o) & (op.valid_i_test)):
            m.next = next_state
            # op is latched in from FPNumIn class on same ack/stb
            m.d.comb += ack.eq(0)
        with m.Else():
            m.d.comb += ack.eq(1)
        return [res, ack]

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
            m.d.sync += a.e.eq(a.fp.N126)  # limit a exponent
        with m.Else():
            m.d.sync += a.m[-1].eq(1)  # set top mantissa bit

    def op_normalise(self, m, op, next_state):
        """ operand normalisation
            NOTE: just like "align", this one keeps going round every clock
                  until the result's exponent is within acceptable "range"
        """
        with m.If((op.m[-1] == 0)):  # check last bit of mantissa
            m.d.sync += [
                op.e.eq(op.e - 1),  # DECREASE exponent
                op.m.eq(op.m << 1),  # shift mantissa UP
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
        with m.If((z.m[-1] == 0) & (z.e > z.fp.N126)):
            m.d.sync += [
                z.e.eq(z.e - 1),  # DECREASE exponent
                z.m.eq(z.m << 1),  # shift mantissa UP
                z.m[0].eq(of.guard),       # steal guard bit (was tot[2])
                of.guard.eq(of.round_bit),  # steal round_bit (was tot[1])
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
        with m.If(z.e < z.fp.N126):
            m.d.sync += [
                z.e.eq(z.e + 1),  # INCREASE exponent
                z.m.eq(z.m >> 1),  # shift mantissa DOWN
                of.guard.eq(z.m[0]),
                of.m0.eq(z.m[1]),
                of.round_bit.eq(of.guard),
                of.sticky.eq(of.sticky | of.round_bit)
            ]
        with m.Else():
            m.next = next_state

    def roundz(self, m, z, roundz):
        """ performs rounding on the output.  TODO: different kinds of rounding
        """
        with m.If(roundz):
            m.d.sync += z.m.eq(z.m + 1)  # mantissa rounds up
            with m.If(z.m == z.fp.m1s):  # all 1s
                m.d.sync += z.e.eq(z.e + 1)  # exponent rounds up

    def corrections(self, m, z, next_state):
        """ denormalisation and sign-bug corrections
        """
        m.next = next_state
        # denormalised, correct exponent to zero
        with m.If(z.is_denormalised):
            m.d.sync += z.e.eq(z.fp.N127)

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
        with m.If(out_z.valid_o & out_z.ready_i_test):
            m.d.sync += out_z.valid_o.eq(0)
            m.next = next_state
        with m.Else():
            m.d.sync += out_z.valid_o.eq(1)


class FPState(FPBase):
    def __init__(self, state_from):
        self.state_from = state_from

    def set_inputs(self, inputs):
        self.inputs = inputs
        for k, v in inputs.items():
            setattr(self, k, v)

    def set_outputs(self, outputs):
        self.outputs = outputs
        for k, v in outputs.items():
            setattr(self, k, v)


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


if __name__ == '__main__':
    unittest.main()

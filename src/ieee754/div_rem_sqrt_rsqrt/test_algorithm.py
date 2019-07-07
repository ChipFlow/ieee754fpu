# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from nmigen.hdl.ast import Const
from .algorithm import (div_rem, UnsignedDivRem, DivRem,
                        Fixed, RootRemainder, fixed_sqrt, FixedSqrt,
                        fixed_rsqrt, FixedRSqrt, Operation,
                        FixedUDivRemSqrtRSqrt)
import unittest
import math


class TestDivRemFn(unittest.TestCase):
    def test_signed(self):
        test_cases = [
            # numerator, denominator, quotient, remainder
            (-8, -8, 1, 0),
            (-7, -8, 0, -7),
            (-6, -8, 0, -6),
            (-5, -8, 0, -5),
            (-4, -8, 0, -4),
            (-3, -8, 0, -3),
            (-2, -8, 0, -2),
            (-1, -8, 0, -1),
            (0, -8, 0, 0),
            (1, -8, 0, 1),
            (2, -8, 0, 2),
            (3, -8, 0, 3),
            (4, -8, 0, 4),
            (5, -8, 0, 5),
            (6, -8, 0, 6),
            (7, -8, 0, 7),
            (-8, -7, 1, -1),
            (-7, -7, 1, 0),
            (-6, -7, 0, -6),
            (-5, -7, 0, -5),
            (-4, -7, 0, -4),
            (-3, -7, 0, -3),
            (-2, -7, 0, -2),
            (-1, -7, 0, -1),
            (0, -7, 0, 0),
            (1, -7, 0, 1),
            (2, -7, 0, 2),
            (3, -7, 0, 3),
            (4, -7, 0, 4),
            (5, -7, 0, 5),
            (6, -7, 0, 6),
            (7, -7, -1, 0),
            (-8, -6, 1, -2),
            (-7, -6, 1, -1),
            (-6, -6, 1, 0),
            (-5, -6, 0, -5),
            (-4, -6, 0, -4),
            (-3, -6, 0, -3),
            (-2, -6, 0, -2),
            (-1, -6, 0, -1),
            (0, -6, 0, 0),
            (1, -6, 0, 1),
            (2, -6, 0, 2),
            (3, -6, 0, 3),
            (4, -6, 0, 4),
            (5, -6, 0, 5),
            (6, -6, -1, 0),
            (7, -6, -1, 1),
            (-8, -5, 1, -3),
            (-7, -5, 1, -2),
            (-6, -5, 1, -1),
            (-5, -5, 1, 0),
            (-4, -5, 0, -4),
            (-3, -5, 0, -3),
            (-2, -5, 0, -2),
            (-1, -5, 0, -1),
            (0, -5, 0, 0),
            (1, -5, 0, 1),
            (2, -5, 0, 2),
            (3, -5, 0, 3),
            (4, -5, 0, 4),
            (5, -5, -1, 0),
            (6, -5, -1, 1),
            (7, -5, -1, 2),
            (-8, -4, 2, 0),
            (-7, -4, 1, -3),
            (-6, -4, 1, -2),
            (-5, -4, 1, -1),
            (-4, -4, 1, 0),
            (-3, -4, 0, -3),
            (-2, -4, 0, -2),
            (-1, -4, 0, -1),
            (0, -4, 0, 0),
            (1, -4, 0, 1),
            (2, -4, 0, 2),
            (3, -4, 0, 3),
            (4, -4, -1, 0),
            (5, -4, -1, 1),
            (6, -4, -1, 2),
            (7, -4, -1, 3),
            (-8, -3, 2, -2),
            (-7, -3, 2, -1),
            (-6, -3, 2, 0),
            (-5, -3, 1, -2),
            (-4, -3, 1, -1),
            (-3, -3, 1, 0),
            (-2, -3, 0, -2),
            (-1, -3, 0, -1),
            (0, -3, 0, 0),
            (1, -3, 0, 1),
            (2, -3, 0, 2),
            (3, -3, -1, 0),
            (4, -3, -1, 1),
            (5, -3, -1, 2),
            (6, -3, -2, 0),
            (7, -3, -2, 1),
            (-8, -2, 4, 0),
            (-7, -2, 3, -1),
            (-6, -2, 3, 0),
            (-5, -2, 2, -1),
            (-4, -2, 2, 0),
            (-3, -2, 1, -1),
            (-2, -2, 1, 0),
            (-1, -2, 0, -1),
            (0, -2, 0, 0),
            (1, -2, 0, 1),
            (2, -2, -1, 0),
            (3, -2, -1, 1),
            (4, -2, -2, 0),
            (5, -2, -2, 1),
            (6, -2, -3, 0),
            (7, -2, -3, 1),
            (-8, -1, -8, 0),  # overflows and wraps around
            (-7, -1, 7, 0),
            (-6, -1, 6, 0),
            (-5, -1, 5, 0),
            (-4, -1, 4, 0),
            (-3, -1, 3, 0),
            (-2, -1, 2, 0),
            (-1, -1, 1, 0),
            (0, -1, 0, 0),
            (1, -1, -1, 0),
            (2, -1, -2, 0),
            (3, -1, -3, 0),
            (4, -1, -4, 0),
            (5, -1, -5, 0),
            (6, -1, -6, 0),
            (7, -1, -7, 0),
            (-8, 0, -1, -8),
            (-7, 0, -1, -7),
            (-6, 0, -1, -6),
            (-5, 0, -1, -5),
            (-4, 0, -1, -4),
            (-3, 0, -1, -3),
            (-2, 0, -1, -2),
            (-1, 0, -1, -1),
            (0, 0, -1, 0),
            (1, 0, -1, 1),
            (2, 0, -1, 2),
            (3, 0, -1, 3),
            (4, 0, -1, 4),
            (5, 0, -1, 5),
            (6, 0, -1, 6),
            (7, 0, -1, 7),
            (-8, 1, -8, 0),
            (-7, 1, -7, 0),
            (-6, 1, -6, 0),
            (-5, 1, -5, 0),
            (-4, 1, -4, 0),
            (-3, 1, -3, 0),
            (-2, 1, -2, 0),
            (-1, 1, -1, 0),
            (0, 1, 0, 0),
            (1, 1, 1, 0),
            (2, 1, 2, 0),
            (3, 1, 3, 0),
            (4, 1, 4, 0),
            (5, 1, 5, 0),
            (6, 1, 6, 0),
            (7, 1, 7, 0),
            (-8, 2, -4, 0),
            (-7, 2, -3, -1),
            (-6, 2, -3, 0),
            (-5, 2, -2, -1),
            (-4, 2, -2, 0),
            (-3, 2, -1, -1),
            (-2, 2, -1, 0),
            (-1, 2, 0, -1),
            (0, 2, 0, 0),
            (1, 2, 0, 1),
            (2, 2, 1, 0),
            (3, 2, 1, 1),
            (4, 2, 2, 0),
            (5, 2, 2, 1),
            (6, 2, 3, 0),
            (7, 2, 3, 1),
            (-8, 3, -2, -2),
            (-7, 3, -2, -1),
            (-6, 3, -2, 0),
            (-5, 3, -1, -2),
            (-4, 3, -1, -1),
            (-3, 3, -1, 0),
            (-2, 3, 0, -2),
            (-1, 3, 0, -1),
            (0, 3, 0, 0),
            (1, 3, 0, 1),
            (2, 3, 0, 2),
            (3, 3, 1, 0),
            (4, 3, 1, 1),
            (5, 3, 1, 2),
            (6, 3, 2, 0),
            (7, 3, 2, 1),
            (-8, 4, -2, 0),
            (-7, 4, -1, -3),
            (-6, 4, -1, -2),
            (-5, 4, -1, -1),
            (-4, 4, -1, 0),
            (-3, 4, 0, -3),
            (-2, 4, 0, -2),
            (-1, 4, 0, -1),
            (0, 4, 0, 0),
            (1, 4, 0, 1),
            (2, 4, 0, 2),
            (3, 4, 0, 3),
            (4, 4, 1, 0),
            (5, 4, 1, 1),
            (6, 4, 1, 2),
            (7, 4, 1, 3),
            (-8, 5, -1, -3),
            (-7, 5, -1, -2),
            (-6, 5, -1, -1),
            (-5, 5, -1, 0),
            (-4, 5, 0, -4),
            (-3, 5, 0, -3),
            (-2, 5, 0, -2),
            (-1, 5, 0, -1),
            (0, 5, 0, 0),
            (1, 5, 0, 1),
            (2, 5, 0, 2),
            (3, 5, 0, 3),
            (4, 5, 0, 4),
            (5, 5, 1, 0),
            (6, 5, 1, 1),
            (7, 5, 1, 2),
            (-8, 6, -1, -2),
            (-7, 6, -1, -1),
            (-6, 6, -1, 0),
            (-5, 6, 0, -5),
            (-4, 6, 0, -4),
            (-3, 6, 0, -3),
            (-2, 6, 0, -2),
            (-1, 6, 0, -1),
            (0, 6, 0, 0),
            (1, 6, 0, 1),
            (2, 6, 0, 2),
            (3, 6, 0, 3),
            (4, 6, 0, 4),
            (5, 6, 0, 5),
            (6, 6, 1, 0),
            (7, 6, 1, 1),
            (-8, 7, -1, -1),
            (-7, 7, -1, 0),
            (-6, 7, 0, -6),
            (-5, 7, 0, -5),
            (-4, 7, 0, -4),
            (-3, 7, 0, -3),
            (-2, 7, 0, -2),
            (-1, 7, 0, -1),
            (0, 7, 0, 0),
            (1, 7, 0, 1),
            (2, 7, 0, 2),
            (3, 7, 0, 3),
            (4, 7, 0, 4),
            (5, 7, 0, 5),
            (6, 7, 0, 6),
            (7, 7, 1, 0),
        ]
        for (n, d, q, r) in test_cases:
            self.assertEqual(div_rem(n, d, 4, True), (q, r))

    def test_unsigned(self):
        for n in range(16):
            for d in range(16):
                if d == 0:
                    q = 16 - 1
                    r = n
                else:
                    # div_rem matches // and % for unsigned integers
                    q = n // d
                    r = n % d
                self.assertEqual(div_rem(n, d, 4, False), (q, r))


class TestUnsignedDivRem(unittest.TestCase):
    def helper(self, log2_radix):
        bit_width = 4
        for n in range(1 << bit_width):
            for d in range(1 << bit_width):
                q, r = div_rem(n, d, bit_width, False)
                with self.subTest(n=n, d=d, q=q, r=r):
                    udr = UnsignedDivRem(n, d, bit_width, log2_radix)
                    for _ in range(250 * bit_width):
                        self.assertEqual(udr.dividend, n)
                        self.assertEqual(udr.divisor, d)
                        self.assertEqual(udr.quotient_times_divisor,
                                         udr.quotient * udr.divisor)
                        self.assertGreaterEqual(udr.dividend,
                                                udr.quotient_times_divisor)
                        if udr.calculate_stage():
                            break
                    else:
                        self.fail("infinite loop")
                    self.assertEqual(udr.dividend, n)
                    self.assertEqual(udr.divisor, d)
                    self.assertEqual(udr.quotient_times_divisor,
                                     udr.quotient * udr.divisor)
                    self.assertGreaterEqual(udr.dividend,
                                            udr.quotient_times_divisor)
                    self.assertEqual(udr.quotient, q)
                    self.assertEqual(udr.remainder, r)

    def test_radix_2(self):
        self.helper(1)

    def test_radix_4(self):
        self.helper(2)

    def test_radix_8(self):
        self.helper(3)

    def test_radix_16(self):
        self.helper(4)


class TestDivRem(unittest.TestCase):
    def helper(self, log2_radix):
        bit_width = 4
        for n in range(1 << bit_width):
            for d in range(1 << bit_width):
                for signed in False, True:
                    n = Const.normalize(n, (bit_width, signed))
                    d = Const.normalize(d, (bit_width, signed))
                    q, r = div_rem(n, d, bit_width, signed)
                    with self.subTest(n=n, d=d, q=q, r=r, signed=signed):
                        dr = DivRem(n, d, bit_width, signed, log2_radix)
                        for _ in range(250 * bit_width):
                            if dr.calculate_stage():
                                break
                        else:
                            self.fail("infinite loop")
                        self.assertEqual(dr.quotient, q)
                        self.assertEqual(dr.remainder, r)

    def test_radix_2(self):
        self.helper(1)

    def test_radix_4(self):
        self.helper(2)

    def test_radix_8(self):
        self.helper(3)

    def test_radix_16(self):
        self.helper(4)


class TestFixed(unittest.TestCase):
    def test_constructor(self):
        value = Fixed(0, 0, 1, False)
        self.assertEqual(value.bits, 0)
        self.assertEqual(value.fract_width, 0)
        self.assertEqual(value.bit_width, 1)
        self.assertEqual(value.signed, False)
        value = Fixed(1, 2, 3, True)
        self.assertEqual(value.bits, -4)
        self.assertEqual(value.fract_width, 2)
        self.assertEqual(value.bit_width, 3)
        self.assertEqual(value.signed, True)
        value = Fixed(1, 2, 4, True)
        self.assertEqual(value.bits, 4)
        self.assertEqual(value.fract_width, 2)
        self.assertEqual(value.bit_width, 4)
        self.assertEqual(value.signed, True)
        value = Fixed(1.25, 4, 8, True)
        self.assertEqual(value.bits, 0x14)
        self.assertEqual(value.fract_width, 4)
        self.assertEqual(value.bit_width, 8)
        self.assertEqual(value.signed, True)
        value = Fixed(Fixed(2, 0, 12, False), 4, 8, True)
        self.assertEqual(value.bits, 0x20)
        self.assertEqual(value.fract_width, 4)
        self.assertEqual(value.bit_width, 8)
        self.assertEqual(value.signed, True)
        value = Fixed(0x2FF / 2 ** 8, 8, 12, False)
        self.assertEqual(value.bits, 0x2FF)
        self.assertEqual(value.fract_width, 8)
        self.assertEqual(value.bit_width, 12)
        self.assertEqual(value.signed, False)
        value = Fixed(value, 4, 8, True)
        self.assertEqual(value.bits, 0x2F)
        self.assertEqual(value.fract_width, 4)
        self.assertEqual(value.bit_width, 8)
        self.assertEqual(value.signed, True)

    def helper_tst_from_bits(self, bit_width, fract_width):
        signed = False
        for bits in range(1 << bit_width):
            with self.subTest(bit_width=bit_width,
                              fract_width=fract_width,
                              signed=signed,
                              bits=hex(bits)):
                value = Fixed.from_bits(bits, fract_width, bit_width, signed)
                self.assertEqual(value.bit_width, bit_width)
                self.assertEqual(value.fract_width, fract_width)
                self.assertEqual(value.signed, signed)
                self.assertEqual(value.bits, bits)
        signed = True
        for bits in range(-1 << (bit_width - 1), 1 << (bit_width - 1)):
            with self.subTest(bit_width=bit_width,
                              fract_width=fract_width,
                              signed=signed,
                              bits=hex(bits)):
                value = Fixed.from_bits(bits, fract_width, bit_width, signed)
                self.assertEqual(value.bit_width, bit_width)
                self.assertEqual(value.fract_width, fract_width)
                self.assertEqual(value.signed, signed)
                self.assertEqual(value.bits, bits)

    def test_from_bits(self):
        for bit_width in range(1, 5):
            for fract_width in range(bit_width):
                self.helper_tst_from_bits(bit_width, fract_width)

    def test_repr(self):
        self.assertEqual(repr(Fixed.from_bits(1, 2, 3, False)),
                         "Fixed.from_bits(1, 2, 3, False)")
        self.assertEqual(repr(Fixed.from_bits(-4, 2, 3, True)),
                         "Fixed.from_bits(-4, 2, 3, True)")
        self.assertEqual(repr(Fixed.from_bits(-4, 7, 10, True)),
                         "Fixed.from_bits(-4, 7, 10, True)")

    def test_trunc(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            with self.subTest(value=repr(value)):
                self.assertEqual(math.trunc(value), math.trunc(i / 4))

    def test_int(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            with self.subTest(value=repr(value)):
                self.assertEqual(int(value), math.trunc(value))

    def test_float(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            with self.subTest(value=repr(value)):
                self.assertEqual(float(value), i / 4)

    def test_floor(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            with self.subTest(value=repr(value)):
                self.assertEqual(math.floor(value), math.floor(i / 4))

    def test_ceil(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            with self.subTest(value=repr(value)):
                self.assertEqual(math.ceil(value), math.ceil(i / 4))

    def test_neg(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            expected = -i / 4 if i != -8 else -2.0  # handle wrap-around
            with self.subTest(value=repr(value)):
                self.assertEqual(float(-value), expected)

    def test_pos(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            with self.subTest(value=repr(value)):
                value = +value
                self.assertEqual(value.bits, i)

    def test_abs(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            expected = abs(i) / 4 if i != -8 else -2.0  # handle wrap-around
            with self.subTest(value=repr(value)):
                self.assertEqual(float(abs(value)), expected)

    def test_not(self):
        for i in range(-8, 8):
            value = Fixed.from_bits(i, 2, 4, True)
            with self.subTest(value=repr(value)):
                self.assertEqual(float(~value), (~i) / 4)

    @staticmethod
    def get_test_values(max_bit_width, include_int):
        for signed in False, True:
            if include_int:
                for bits in range(1 << max_bit_width):
                    int_value = Const.normalize(bits, (max_bit_width, signed))
                    yield int_value
            for bit_width in range(1, max_bit_width):
                for fract_width in range(bit_width + 1):
                    for bits in range(1 << bit_width):
                        yield Fixed.from_bits(bits,
                                              fract_width,
                                              bit_width,
                                              signed)

    def binary_op_test_helper(self,
                              operation,
                              is_fixed=True,
                              width_combine_op=max,
                              adjust_bits_op=None):
        def default_adjust_bits_op(bits, out_fract_width, in_fract_width):
            return bits << (out_fract_width - in_fract_width)
        if adjust_bits_op is None:
            adjust_bits_op = default_adjust_bits_op
        max_bit_width = 5
        for lhs in self.get_test_values(max_bit_width, True):
            lhs_is_int = isinstance(lhs, int)
            for rhs in self.get_test_values(max_bit_width, not lhs_is_int):
                rhs_is_int = isinstance(rhs, int)
                if lhs_is_int:
                    assert not rhs_is_int
                    lhs_int = adjust_bits_op(lhs, rhs.fract_width, 0)
                    int_result = operation(lhs_int, rhs.bits)
                    if is_fixed:
                        expected = Fixed.from_bits(int_result,
                                                   rhs.fract_width,
                                                   rhs.bit_width,
                                                   rhs.signed)
                    else:
                        expected = int_result
                elif rhs_is_int:
                    rhs_int = adjust_bits_op(rhs, lhs.fract_width, 0)
                    int_result = operation(lhs.bits, rhs_int)
                    if is_fixed:
                        expected = Fixed.from_bits(int_result,
                                                   lhs.fract_width,
                                                   lhs.bit_width,
                                                   lhs.signed)
                    else:
                        expected = int_result
                elif lhs.signed != rhs.signed:
                    continue
                else:
                    fract_width = width_combine_op(lhs.fract_width,
                                                   rhs.fract_width)
                    int_width = width_combine_op(lhs.bit_width
                                                 - lhs.fract_width,
                                                 rhs.bit_width
                                                 - rhs.fract_width)
                    bit_width = fract_width + int_width
                    lhs_int = adjust_bits_op(lhs.bits,
                                             fract_width,
                                             lhs.fract_width)
                    rhs_int = adjust_bits_op(rhs.bits,
                                             fract_width,
                                             rhs.fract_width)
                    int_result = operation(lhs_int, rhs_int)
                    if is_fixed:
                        expected = Fixed.from_bits(int_result,
                                                   fract_width,
                                                   bit_width,
                                                   lhs.signed)
                    else:
                        expected = int_result
                with self.subTest(lhs=repr(lhs),
                                  rhs=repr(rhs),
                                  expected=repr(expected)):
                    result = operation(lhs, rhs)
                    if is_fixed:
                        self.assertEqual(result.bit_width, expected.bit_width)
                        self.assertEqual(result.signed, expected.signed)
                        self.assertEqual(result.fract_width,
                                         expected.fract_width)
                        self.assertEqual(result.bits, expected.bits)
                    else:
                        self.assertEqual(result, expected)

    def test_add(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs + rhs)

    def test_sub(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs - rhs)

    def test_and(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs & rhs)

    def test_or(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs | rhs)

    def test_xor(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs ^ rhs)

    def test_mul(self):
        def adjust_bits_op(bits, out_fract_width, in_fract_width):
            return bits
        self.binary_op_test_helper(lambda lhs, rhs: lhs * rhs,
                                   True,
                                   lambda l_width, r_width: l_width + r_width,
                                   adjust_bits_op)

    def test_cmp(self):
        def cmp(lhs, rhs):
            if lhs < rhs:
                return -1
            elif lhs > rhs:
                return 1
            return 0
        self.binary_op_test_helper(cmp, False)

    def test_lt(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs < rhs, False)

    def test_le(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs <= rhs, False)

    def test_eq(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs == rhs, False)

    def test_ne(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs != rhs, False)

    def test_gt(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs > rhs, False)

    def test_ge(self):
        self.binary_op_test_helper(lambda lhs, rhs: lhs >= rhs, False)

    def test_bool(self):
        for v in self.get_test_values(6, False):
            with self.subTest(v=repr(v)):
                self.assertEqual(bool(v), bool(v.bits))

    def test_str(self):
        self.assertEqual(str(Fixed.from_bits(0x1234, 0, 16, False)),
                         "fixed:0x1234.")
        self.assertEqual(str(Fixed.from_bits(-0x1234, 0, 16, True)),
                         "fixed:-0x1234.")
        self.assertEqual(str(Fixed.from_bits(0x12345, 3, 20, True)),
                         "fixed:0x2468.a")
        self.assertEqual(str(Fixed(123.625, 3, 12, True)),
                         "fixed:0x7b.a")

        self.assertEqual(str(Fixed.from_bits(0x1, 0, 20, True)),
                         "fixed:0x1.")
        self.assertEqual(str(Fixed.from_bits(0x2, 1, 20, True)),
                         "fixed:0x1.0")
        self.assertEqual(str(Fixed.from_bits(0x4, 2, 20, True)),
                         "fixed:0x1.0")
        self.assertEqual(str(Fixed.from_bits(0x9, 3, 20, True)),
                         "fixed:0x1.2")
        self.assertEqual(str(Fixed.from_bits(0x12, 4, 20, True)),
                         "fixed:0x1.2")
        self.assertEqual(str(Fixed.from_bits(0x24, 5, 20, True)),
                         "fixed:0x1.20")
        self.assertEqual(str(Fixed.from_bits(0x48, 6, 20, True)),
                         "fixed:0x1.20")
        self.assertEqual(str(Fixed.from_bits(0x91, 7, 20, True)),
                         "fixed:0x1.22")
        self.assertEqual(str(Fixed.from_bits(0x123, 8, 20, True)),
                         "fixed:0x1.23")
        self.assertEqual(str(Fixed.from_bits(0x246, 9, 20, True)),
                         "fixed:0x1.230")
        self.assertEqual(str(Fixed.from_bits(0x48d, 10, 20, True)),
                         "fixed:0x1.234")
        self.assertEqual(str(Fixed.from_bits(0x91a, 11, 20, True)),
                         "fixed:0x1.234")
        self.assertEqual(str(Fixed.from_bits(0x1234, 12, 20, True)),
                         "fixed:0x1.234")
        self.assertEqual(str(Fixed.from_bits(0x2468, 13, 20, True)),
                         "fixed:0x1.2340")
        self.assertEqual(str(Fixed.from_bits(0x48d1, 14, 20, True)),
                         "fixed:0x1.2344")
        self.assertEqual(str(Fixed.from_bits(0x91a2, 15, 20, True)),
                         "fixed:0x1.2344")
        self.assertEqual(str(Fixed.from_bits(0x12345, 16, 20, True)),
                         "fixed:0x1.2345")
        self.assertEqual(str(Fixed.from_bits(0x2468a, 17, 20, True)),
                         "fixed:0x1.23450")
        self.assertEqual(str(Fixed.from_bits(0x48d14, 18, 20, True)),
                         "fixed:0x1.23450")
        self.assertEqual(str(Fixed.from_bits(0x91a28, 19, 20, True)),
                         "fixed:-0x0.dcbb0")
        self.assertEqual(str(Fixed.from_bits(0x91a28, 19, 20, False)),
                         "fixed:0x1.23450")


class TestFixedSqrtFn(unittest.TestCase):
    def test_on_ints(self):
        for radicand in range(-1, 32):
            if radicand < 0:
                expected = None
            else:
                root = math.floor(math.sqrt(radicand))
                remainder = radicand - root * root
                expected = RootRemainder(root, remainder)
            with self.subTest(radicand=radicand, expected=expected):
                self.assertEqual(repr(fixed_sqrt(radicand)), repr(expected))
        radicand = 2 << 64
        root = 0x16A09E667
        remainder = radicand - root * root
        expected = RootRemainder(root, remainder)
        with self.subTest(radicand=radicand, expected=expected):
            self.assertEqual(repr(fixed_sqrt(radicand)), repr(expected))

    def test_on_fixed(self):
        for signed in False, True:
            for bit_width in range(1, 10):
                for fract_width in range(bit_width):
                    for bits in range(1 << bit_width):
                        radicand = Fixed.from_bits(bits,
                                                   fract_width,
                                                   bit_width,
                                                   signed)
                        if radicand < 0:
                            continue
                        root = radicand.with_value(math.sqrt(float(radicand)))
                        remainder = radicand - root * root
                        expected = RootRemainder(root, remainder)
                        with self.subTest(radicand=repr(radicand),
                                          expected=repr(expected)):
                            self.assertEqual(repr(fixed_sqrt(radicand)),
                                             repr(expected))

    def test_misc_cases(self):
        test_cases = [
            # radicand, expected
            (2 << 64, str(RootRemainder(0x16A09E667, 0x2B164C28F))),
            (Fixed(2, 30, 32, False),
             "RootRemainder(fixed:0x1.6a09e664, fixed:0x0.0000000b2da028f)")
        ]
        for radicand, expected in test_cases:
            with self.subTest(radicand=str(radicand), expected=expected):
                self.assertEqual(str(fixed_sqrt(radicand)), expected)


class TestFixedSqrt(unittest.TestCase):
    def helper(self, log2_radix):
        for bit_width in range(1, 8):
            for fract_width in range(bit_width):
                for radicand_bits in range(1 << bit_width):
                    radicand = Fixed.from_bits(radicand_bits,
                                               fract_width,
                                               bit_width,
                                               False)
                    root_remainder = fixed_sqrt(radicand)
                    with self.subTest(radicand=repr(radicand),
                                      root_remainder=repr(root_remainder),
                                      log2_radix=log2_radix):
                        obj = FixedSqrt(radicand, log2_radix)
                        for _ in range(250 * bit_width):
                            self.assertEqual(obj.root * obj.root,
                                             obj.root_squared)
                            self.assertGreaterEqual(obj.radicand,
                                                    obj.root_squared)
                            if obj.calculate_stage():
                                break
                        else:
                            self.fail("infinite loop")
                        self.assertEqual(obj.root * obj.root,
                                         obj.root_squared)
                        self.assertGreaterEqual(obj.radicand,
                                                obj.root_squared)
                        self.assertEqual(obj.remainder,
                                         obj.radicand - obj.root_squared)
                        self.assertEqual(obj.root, root_remainder.root)
                        self.assertEqual(obj.remainder,
                                         root_remainder.remainder)

    def test_radix_2(self):
        self.helper(1)

    def test_radix_4(self):
        self.helper(2)

    def test_radix_8(self):
        self.helper(3)

    def test_radix_16(self):
        self.helper(4)


class TestFixedRSqrtFn(unittest.TestCase):
    def test2(self):
        for bits in range(1, 1 << 5):
            radicand = Fixed.from_bits(bits, 5, 12, False)
            float_root = 1 / math.sqrt(float(radicand))
            root = radicand.with_value(float_root)
            remainder = 1 - root * root * radicand
            expected = RootRemainder(root, remainder)
            with self.subTest(radicand=repr(radicand),
                              expected=repr(expected)):
                self.assertEqual(repr(fixed_rsqrt(radicand)),
                                 repr(expected))

    def test(self):
        for signed in False, True:
            for bit_width in range(1, 10):
                for fract_width in range(bit_width):
                    for bits in range(1 << bit_width):
                        radicand = Fixed.from_bits(bits,
                                                   fract_width,
                                                   bit_width,
                                                   signed)
                        if radicand <= 0:
                            continue
                        float_root = 1 / math.sqrt(float(radicand))
                        max_value = radicand.with_bits(
                            (1 << (bit_width - signed)) - 1)
                        if float_root > float(max_value):
                            root = max_value
                        else:
                            root = radicand.with_value(float_root)
                        remainder = 1 - root * root * radicand
                        expected = RootRemainder(root, remainder)
                        with self.subTest(radicand=repr(radicand),
                                          expected=repr(expected)):
                            self.assertEqual(repr(fixed_rsqrt(radicand)),
                                             repr(expected))

    def test_misc_cases(self):
        test_cases = [
            # radicand, expected
            (Fixed(0.5, 30, 32, False),
             "RootRemainder(fixed:0x1.6a09e664, "
             "fixed:0x0.0000000596d014780000000)")
        ]
        for radicand, expected in test_cases:
            with self.subTest(radicand=str(radicand), expected=expected):
                self.assertEqual(str(fixed_rsqrt(radicand)), expected)


class TestFixedRSqrt(unittest.TestCase):
    def helper(self, log2_radix):
        for bit_width in range(1, 8):
            for fract_width in range(bit_width):
                for radicand_bits in range(1, 1 << bit_width):
                    radicand = Fixed.from_bits(radicand_bits,
                                               fract_width,
                                               bit_width,
                                               False)
                    root_remainder = fixed_rsqrt(radicand)
                    with self.subTest(radicand=repr(radicand),
                                      root_remainder=repr(root_remainder),
                                      log2_radix=log2_radix):
                        obj = FixedRSqrt(radicand, log2_radix)
                        for _ in range(250 * bit_width):
                            self.assertEqual(obj.radicand * obj.root,
                                             obj.radicand_root)
                            self.assertEqual(obj.radicand_root * obj.root,
                                             obj.radicand_root_squared)
                            self.assertGreaterEqual(1,
                                                    obj.radicand_root_squared)
                            if obj.calculate_stage():
                                break
                        else:
                            self.fail("infinite loop")
                        self.assertEqual(obj.radicand * obj.root,
                                         obj.radicand_root)
                        self.assertEqual(obj.radicand_root * obj.root,
                                         obj.radicand_root_squared)
                        self.assertGreaterEqual(1,
                                                obj.radicand_root_squared)
                        self.assertEqual(obj.remainder,
                                         1 - obj.radicand_root_squared)
                        self.assertEqual(obj.root, root_remainder.root)
                        self.assertEqual(obj.remainder,
                                         root_remainder.remainder)

    def test_radix_2(self):
        self.helper(1)

    def test_radix_4(self):
        self.helper(2)

    def test_radix_8(self):
        self.helper(3)

    def test_radix_16(self):
        self.helper(4)


class TestFixedUDivRemSqrtRSqrt(unittest.TestCase):
    @staticmethod
    def show_fixed(bits, fract_width, bit_width):
        fixed = Fixed.from_bits(bits, fract_width, bit_width, False)
        return f"{str(fixed)}:{repr(fixed)}"

    def check_invariants(self,
                         dividend,
                         divisor_radicand,
                         operation,
                         bit_width,
                         fract_width,
                         log2_radix,
                         obj):
        self.assertEqual(obj.dividend, dividend)
        self.assertEqual(obj.divisor_radicand, divisor_radicand)
        self.assertEqual(obj.operation, operation)
        self.assertEqual(obj.bit_width, bit_width)
        self.assertEqual(obj.fract_width, fract_width)
        self.assertEqual(obj.log2_radix, log2_radix)
        self.assertEqual(obj.root_times_radicand,
                         obj.quotient_root * obj.divisor_radicand)
        self.assertGreaterEqual(obj.compare_lhs, obj.compare_rhs)
        self.assertEqual(obj.remainder, obj.compare_lhs - obj.compare_rhs)
        if operation is Operation.UDivRem:
            self.assertEqual(obj.compare_lhs, obj.dividend << fract_width)
            self.assertEqual(obj.compare_rhs,
                             (obj.quotient_root * obj.divisor_radicand)
                             << fract_width)
        elif operation is Operation.SqrtRem:
            self.assertEqual(obj.compare_lhs,
                             obj.divisor_radicand << (fract_width * 2))
            self.assertEqual(obj.compare_rhs,
                             (obj.quotient_root * obj.quotient_root)
                             << fract_width)
        else:
            assert operation is Operation.RSqrtRem
            self.assertEqual(obj.compare_lhs,
                             1 << (fract_width * 3))
            self.assertEqual(obj.compare_rhs,
                             obj.quotient_root * obj.quotient_root
                             * obj.divisor_radicand)

    def handle_case(self,
                    dividend,
                    divisor_radicand,
                    operation,
                    bit_width,
                    fract_width,
                    log2_radix):
        dividend_str = self.show_fixed(dividend,
                                       fract_width * 2,
                                       bit_width + fract_width)
        divisor_radicand_str = self.show_fixed(divisor_radicand,
                                               fract_width,
                                               bit_width)
        with self.subTest(dividend=dividend_str,
                          divisor_radicand=divisor_radicand_str,
                          operation=operation.name,
                          bit_width=bit_width,
                          fract_width=fract_width,
                          log2_radix=log2_radix):
            if operation is Operation.UDivRem:
                if divisor_radicand == 0:
                    return
                quotient_root, remainder = div_rem(dividend,
                                                   divisor_radicand,
                                                   bit_width * 3,
                                                   False)
                remainder <<= fract_width
            elif operation is Operation.SqrtRem:
                root_remainder = fixed_sqrt(Fixed.from_bits(divisor_radicand,
                                                            fract_width,
                                                            bit_width,
                                                            False))
                self.assertEqual(root_remainder.root.bit_width,
                                 bit_width)
                self.assertEqual(root_remainder.root.fract_width,
                                 fract_width)
                self.assertEqual(root_remainder.remainder.bit_width,
                                 bit_width * 2)
                self.assertEqual(root_remainder.remainder.fract_width,
                                 fract_width * 2)
                quotient_root = root_remainder.root.bits
                remainder = root_remainder.remainder.bits << fract_width
            else:
                assert operation is Operation.RSqrtRem
                if divisor_radicand == 0:
                    return
                root_remainder = fixed_rsqrt(Fixed.from_bits(divisor_radicand,
                                                             fract_width,
                                                             bit_width,
                                                             False))
                self.assertEqual(root_remainder.root.bit_width,
                                 bit_width)
                self.assertEqual(root_remainder.root.fract_width,
                                 fract_width)
                self.assertEqual(root_remainder.remainder.bit_width,
                                 bit_width * 3)
                self.assertEqual(root_remainder.remainder.fract_width,
                                 fract_width * 3)
                quotient_root = root_remainder.root.bits
                remainder = root_remainder.remainder.bits
            if quotient_root >= (1 << bit_width):
                return
            quotient_root_str = self.show_fixed(quotient_root,
                                                fract_width,
                                                bit_width)
            remainder_str = self.show_fixed(remainder,
                                            fract_width * 3,
                                            bit_width * 3)
            with self.subTest(quotient_root=quotient_root_str,
                              remainder=remainder_str):
                obj = FixedUDivRemSqrtRSqrt(dividend,
                                            divisor_radicand,
                                            operation,
                                            bit_width,
                                            fract_width,
                                            log2_radix)
                for _ in range(250 * bit_width):
                    self.check_invariants(dividend,
                                          divisor_radicand,
                                          operation,
                                          bit_width,
                                          fract_width,
                                          log2_radix,
                                          obj)
                    if obj.calculate_stage():
                        break
                else:
                    self.fail("infinite loop")
                self.check_invariants(dividend,
                                      divisor_radicand,
                                      operation,
                                      bit_width,
                                      fract_width,
                                      log2_radix,
                                      obj)
                self.assertEqual(obj.quotient_root, quotient_root)
                self.assertEqual(obj.remainder, remainder)

    def helper(self, log2_radix, operation):
        bit_width_range = range(1, 8)
        if operation is Operation.UDivRem:
            bit_width_range = range(1, 6)
        for bit_width in bit_width_range:
            for fract_width in range(bit_width):
                for divisor_radicand in range(1 << bit_width):
                    dividend_range = range(1)
                    if operation is Operation.UDivRem:
                        dividend_range = range(1 << (bit_width + fract_width))
                    for dividend in dividend_range:
                        self.handle_case(dividend,
                                         divisor_radicand,
                                         operation,
                                         bit_width,
                                         fract_width,
                                         log2_radix)

    def test_radix_2_UDiv(self):
        self.helper(1, Operation.UDivRem)

    def test_radix_4_UDiv(self):
        self.helper(2, Operation.UDivRem)

    def test_radix_8_UDiv(self):
        self.helper(3, Operation.UDivRem)

    def test_radix_16_UDiv(self):
        self.helper(4, Operation.UDivRem)

    def test_radix_2_Sqrt(self):
        self.helper(1, Operation.SqrtRem)

    def test_radix_4_Sqrt(self):
        self.helper(2, Operation.SqrtRem)

    def test_radix_8_Sqrt(self):
        self.helper(3, Operation.SqrtRem)

    def test_radix_16_Sqrt(self):
        self.helper(4, Operation.SqrtRem)

    def test_radix_2_RSqrt(self):
        self.helper(1, Operation.RSqrtRem)

    def test_radix_4_RSqrt(self):
        self.helper(2, Operation.RSqrtRem)

    def test_radix_8_RSqrt(self):
        self.helper(3, Operation.RSqrtRem)

    def test_radix_16_RSqrt(self):
        self.helper(4, Operation.RSqrtRem)

    def test_int_div(self):
        bit_width = 8
        fract_width = 4
        log2_radix = 3
        for dividend in range(1 << bit_width):
            for divisor in range(1, 1 << bit_width):
                obj = FixedUDivRemSqrtRSqrt(dividend,
                                            divisor,
                                            Operation.UDivRem,
                                            bit_width,
                                            fract_width,
                                            log2_radix)
                obj.calculate()
                quotient, remainder = div_rem(dividend,
                                              divisor,
                                              bit_width,
                                              False)
                shifted_remainder = remainder << fract_width
                with self.subTest(dividend=dividend,
                                  divisor=divisor,
                                  quotient=quotient,
                                  remainder=remainder,
                                  shifted_remainder=shifted_remainder):
                    self.assertEqual(obj.quotient_root, quotient)
                    self.assertEqual(obj.remainder, shifted_remainder)

    def test_fract_div(self):
        bit_width = 8
        fract_width = 4
        log2_radix = 3
        for dividend in range(1 << bit_width):
            for divisor in range(1, 1 << bit_width):
                obj = FixedUDivRemSqrtRSqrt(dividend << fract_width,
                                            divisor,
                                            Operation.UDivRem,
                                            bit_width,
                                            fract_width,
                                            log2_radix)
                obj.calculate()
                quotient = (dividend << fract_width) // divisor
                if quotient >= (1 << bit_width):
                    continue
                remainder = (dividend << fract_width) % divisor
                shifted_remainder = remainder << fract_width
                with self.subTest(dividend=dividend,
                                  divisor=divisor,
                                  quotient=quotient,
                                  remainder=remainder,
                                  shifted_remainder=shifted_remainder):
                    self.assertEqual(obj.quotient_root, quotient)
                    self.assertEqual(obj.remainder, shifted_remainder)

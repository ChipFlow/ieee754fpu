# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

from nmigen.hdl.ast import Const
from .algorithm import (div_rem, UnsignedDivRem, DivRem,
                        Fixed, fixed_sqrt, FixedSqrt, fixed_rsqrt, FixedRSqrt)
import unittest


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
                        self.assertEqual(n, udr.quotient * udr.divisor
                                         + udr.remainder)
                        if udr.calculate_stage():
                            break
                    else:
                        self.fail("infinite loop")
                    self.assertEqual(n, udr.quotient * udr.divisor
                                     + udr.remainder)
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

# FIXME: add tests for Fract, fract_sqrt, FractSqrt, fract_rsqrt, and FractRSqrt

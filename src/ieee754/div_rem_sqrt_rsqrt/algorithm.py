# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

""" Algorithms for div/rem/sqrt/rsqrt.

code for simulating/testing the various algorithms
"""

from nmigen.hdl.ast import Const


def div_rem(dividend, divisor, bit_width, signed):
    """ Compute the quotient/remainder following the RISC-V M extension.

    NOT the same as the // or % operators
    """
    dividend = Const.normalize(dividend, (bit_width, signed))
    divisor = Const.normalize(divisor, (bit_width, signed))
    if divisor == 0:
        quotient = -1
        remainder = dividend
    else:
        quotient = abs(dividend) // abs(divisor)
        remainder = abs(dividend) % abs(divisor)
        if (dividend < 0) != (divisor < 0):
            quotient = -quotient
        if dividend < 0:
            remainder = -remainder
    quotient = Const.normalize(quotient, (bit_width, signed))
    remainder = Const.normalize(remainder, (bit_width, signed))
    return quotient, remainder


class UnsignedDivRem:
    """ Unsigned integer division/remainder following the RISC-V M extension.

    NOT the same as the // or % operators

    :attribute remainder: the remainder and/or dividend
    :attribute divisor: the divisor
    :attribute bit_width: the bit width of the inputs/outputs
    :attribute log2_radix: the base-2 log of the division radix. The number of
        bits of quotient that are calculated per pipeline stage.
    :attribute quotient: the quotient
    :attribute current_shift: the current bit index
    """

    def __init__(self, dividend, divisor, bit_width, log2_radix=3):
        """ Create an UnsignedDivRem.

        :param dividend: the dividend/numerator
        :param divisor: the divisor/denominator
        :param bit_width: the bit width of the inputs/outputs
        :param log2_radix: the base-2 log of the division radix. The number of
            bits of quotient that are calculated per pipeline stage.
        """
        self.remainder = Const.normalize(dividend, (bit_width, False))
        self.divisor = Const.normalize(divisor, (bit_width, False))
        self.bit_width = bit_width
        self.log2_radix = log2_radix
        self.quotient = 0
        self.current_shift = bit_width

    def calculate_stage(self):
        """ Calculate the next pipeline stage of the division.

        :returns bool: True if this is the last pipeline stage.
        """
        if self.current_shift == 0:
            return True
        log2_radix = min(self.log2_radix, self.current_shift)
        assert log2_radix > 0
        self.current_shift -= log2_radix
        radix = 1 << log2_radix
        remainders = []
        for i in range(radix):
            v = (self.divisor * i) << self.current_shift
            remainders.append(self.remainder - v)
        quotient_bits = 0
        for i in range(radix):
            if remainders[i] >= 0:
                quotient_bits = i
        self.remainder = remainders[quotient_bits]
        self.quotient |= quotient_bits << self.current_shift
        return self.current_shift == 0

    def calculate(self):
        """ Calculate the results of the division.

        :returns: self
        """
        while not self.calculate_stage():
            pass
        return self


class DivRem:
    """ integer division/remainder following the RISC-V M extension.

    NOT the same as the // or % operators

    :attribute dividend: the dividend
    :attribute divisor: the divisor
    :attribute signed: if the inputs/outputs are signed instead of unsigned
    :attribute quotient: the quotient
    :attribute remainder: the remainder
    :attribute divider: the base UnsignedDivRem
    """

    def __init__(self, dividend, divisor, bit_width, signed, log2_radix=3):
        """ Create a DivRem.

        :param dividend: the dividend/numerator
        :param divisor: the divisor/denominator
        :param bit_width: the bit width of the inputs/outputs
        :param signed: if the inputs/outputs are signed instead of unsigned
        :param log2_radix: the base-2 log of the division radix. The number of
            bits of quotient that are calculated per pipeline stage.
        """
        self.dividend = Const.normalize(dividend, (bit_width, signed))
        self.divisor = Const.normalize(divisor, (bit_width, signed))
        self.signed = signed
        self.quotient = 0
        self.remainder = 0
        self.divider = UnsignedDivRem(abs(dividend), abs(divisor),
                                      bit_width, log2_radix)

    def calculate_stage(self):
        """ Calculate the next pipeline stage of the division.

        :returns bool: True if this is the last pipeline stage.
        """
        if not self.divider.calculate_stage():
            return False
        divisor_sign = self.divisor < 0
        dividend_sign = self.dividend < 0
        if self.divisor != 0 and divisor_sign != dividend_sign:
            quotient = -self.divider.quotient
        else:
            quotient = self.divider.quotient
        if dividend_sign:
            remainder = -self.divider.remainder
        else:
            remainder = self.divider.remainder
        bit_width = self.divider.bit_width
        self.quotient = Const.normalize(quotient, (bit_width, self.signed))
        self.remainder = Const.normalize(remainder, (bit_width, self.signed))
        return True

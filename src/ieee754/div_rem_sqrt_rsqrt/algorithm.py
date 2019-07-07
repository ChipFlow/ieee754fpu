# SPDX-License-Identifier: LGPL-2.1-or-later
# See Notices.txt for copyright information

""" Algorithms for div/rem/sqrt/rsqrt.

code for simulating/testing the various algorithms
"""

from nmigen.hdl.ast import Const
import math
import enum


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

    :attribute dividend: the dividend
    :attribute remainder: the remainder
    :attribute divisor: the divisor
    :attribute bit_width: the bit width of the inputs/outputs
    :attribute log2_radix: the base-2 log of the division radix. The number of
        bits of quotient that are calculated per pipeline stage.
    :attribute quotient: the quotient
    :attribute quotient_times_divisor: ``quotient * divisor``
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
        self.dividend = Const.normalize(dividend, (bit_width, False))
        self.divisor = Const.normalize(divisor, (bit_width, False))
        self.bit_width = bit_width
        self.log2_radix = log2_radix
        self.quotient = 0
        self.quotient_times_divisor = self.quotient * self.divisor
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
        trial_values = []
        for i in range(radix):
            v = self.quotient_times_divisor
            v += (self.divisor * i) << self.current_shift
            trial_values.append(v)
        quotient_bits = 0
        next_product = self.quotient_times_divisor
        for i in range(radix):
            if self.dividend >= trial_values[i]:
                quotient_bits = i
                next_product = trial_values[i]
        self.quotient_times_divisor = next_product
        self.quotient |= quotient_bits << self.current_shift
        if self.current_shift == 0:
            self.remainder = self.dividend - self.quotient_times_divisor
            return True
        return False

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


class Fixed:
    """ Fixed-point number.

    the value is bits * 2 ** -fract_width

    :attribute bits: the bits of the fixed-point number
    :attribute fract_width: the number of bits in the fractional portion
    :attribute bit_width: the total number of bits
    :attribute signed: if the type is signed
    """

    @staticmethod
    def from_bits(bits, fract_width, bit_width, signed):
        """ Create a new Fixed.

        :param bits: the bits of the fixed-point number
        :param fract_width: the number of bits in the fractional portion
        :param bit_width: the total number of bits
        :param signed: if the type is signed
        """
        retval = Fixed(0, fract_width, bit_width, signed)
        retval.bits = Const.normalize(bits, (bit_width, signed))
        return retval

    def __init__(self, value, fract_width, bit_width, signed):
        """ Create a new Fixed.

        Note: ``value`` is not the same as ``bits``. To put a particular number
        in ``bits``, use ``Fixed.from_bits``.

        :param value: the value of the fixed-point number
        :param fract_width: the number of bits in the fractional portion
        :param bit_width: the total number of bits
        :param signed: if the type is signed
        """
        assert fract_width >= 0
        assert bit_width > 0
        if isinstance(value, Fixed):
            if fract_width < value.fract_width:
                bits = value.bits >> (value.fract_width - fract_width)
            else:
                bits = value.bits << (fract_width - value.fract_width)
        elif isinstance(value, int):
            bits = value << fract_width
        else:
            bits = math.floor(value * 2 ** fract_width)
        self.bits = Const.normalize(bits, (bit_width, signed))
        self.fract_width = fract_width
        self.bit_width = bit_width
        self.signed = signed

    def with_bits(self, bits):
        """ Create a new Fixed with the specified bits.

        :param bits: the new bits.
        :returns Fixed: the new Fixed.
        """
        return self.from_bits(bits,
                              self.fract_width,
                              self.bit_width,
                              self.signed)

    def with_value(self, value):
        """ Create a new Fixed with the specified value.

        :param value: the new value.
        :returns Fixed: the new Fixed.
        """
        return Fixed(value,
                     self.fract_width,
                     self.bit_width,
                     self.signed)

    def __repr__(self):
        """ Get representation."""
        retval = f"Fixed.from_bits({self.bits}, {self.fract_width}, "
        return retval + f"{self.bit_width}, {self.signed})"

    def __trunc__(self):
        """ Truncate to integer."""
        if self.bits < 0:
            return self.__ceil__()
        return self.__floor__()

    def __int__(self):
        """ Truncate to integer."""
        return self.__trunc__()

    def __float__(self):
        """ Convert to float."""
        return self.bits * 2.0 ** -self.fract_width

    def __floor__(self):
        """ Floor to integer."""
        return self.bits >> self.fract_width

    def __ceil__(self):
        """ Ceil to integer."""
        return -((-self.bits) >> self.fract_width)

    def __neg__(self):
        """ Negate."""
        return self.from_bits(-self.bits, self.fract_width,
                              self.bit_width, self.signed)

    def __pos__(self):
        """ Unary Positive."""
        return self

    def __abs__(self):
        """ Absolute Value."""
        return self.from_bits(abs(self.bits), self.fract_width,
                              self.bit_width, self.signed)

    def __invert__(self):
        """ Inverse."""
        return self.from_bits(~self.bits, self.fract_width,
                              self.bit_width, self.signed)

    def _binary_op(self, rhs, operation, full=False):
        """ Handle binary arithmetic operators. """
        if isinstance(rhs, int):
            rhs_fract_width = 0
            rhs_bits = rhs
            int_width = self.bit_width - self.fract_width
        elif isinstance(rhs, Fixed):
            if self.signed != rhs.signed:
                return TypeError("signedness must match")
            rhs_fract_width = rhs.fract_width
            rhs_bits = rhs.bits
            int_width = max(self.bit_width - self.fract_width,
                            rhs.bit_width - rhs.fract_width)
        else:
            return NotImplemented
        fract_width = max(self.fract_width, rhs_fract_width)
        rhs_bits <<= fract_width - rhs_fract_width
        lhs_bits = self.bits << fract_width - self.fract_width
        bit_width = int_width + fract_width
        if full:
            return operation(lhs_bits, rhs_bits,
                             fract_width, bit_width, self.signed)
        bits = operation(lhs_bits, rhs_bits,
                         fract_width)
        return self.from_bits(bits, fract_width, bit_width, self.signed)

    def __add__(self, rhs):
        """ Addition."""
        return self._binary_op(rhs, lambda lhs, rhs, fract_width: lhs + rhs)

    def __radd__(self, lhs):
        """ Reverse Addition."""
        return self.__add__(lhs)

    def __sub__(self, rhs):
        """ Subtraction."""
        return self._binary_op(rhs, lambda lhs, rhs, fract_width: lhs - rhs)

    def __rsub__(self, lhs):
        """ Reverse Subtraction."""
        # note swapped argument and parameter order
        return self._binary_op(lhs, lambda rhs, lhs, fract_width: lhs - rhs)

    def __and__(self, rhs):
        """ Bitwise And."""
        return self._binary_op(rhs, lambda lhs, rhs, fract_width: lhs & rhs)

    def __rand__(self, lhs):
        """ Reverse Bitwise And."""
        return self.__and__(lhs)

    def __or__(self, rhs):
        """ Bitwise Or."""
        return self._binary_op(rhs, lambda lhs, rhs, fract_width: lhs | rhs)

    def __ror__(self, lhs):
        """ Reverse Bitwise Or."""
        return self.__or__(lhs)

    def __xor__(self, rhs):
        """ Bitwise Xor."""
        return self._binary_op(rhs, lambda lhs, rhs, fract_width: lhs ^ rhs)

    def __rxor__(self, lhs):
        """ Reverse Bitwise Xor."""
        return self.__xor__(lhs)

    def __mul__(self, rhs):
        """ Multiplication. """
        if isinstance(rhs, int):
            rhs_fract_width = 0
            rhs_bits = rhs
            int_width = self.bit_width - self.fract_width
        elif isinstance(rhs, Fixed):
            if self.signed != rhs.signed:
                return TypeError("signedness must match")
            rhs_fract_width = rhs.fract_width
            rhs_bits = rhs.bits
            int_width = (self.bit_width - self.fract_width
                         + rhs.bit_width - rhs.fract_width)
        else:
            return NotImplemented
        fract_width = self.fract_width + rhs_fract_width
        bit_width = int_width + fract_width
        bits = self.bits * rhs_bits
        return self.from_bits(bits, fract_width, bit_width, self.signed)

    def __rmul__(self, rhs):
        """ Reverse Multiplication. """
        return self.__mul__(rhs)

    @staticmethod
    def _cmp_impl(lhs, rhs, fract_width, bit_width, signed):
        if lhs < rhs:
            return -1
        elif lhs == rhs:
            return 0
        return 1

    def cmp(self, rhs):
        """ Compare self with rhs.

        :returns int: returns -1 if self is less than rhs, 0 if they're equal,
            and 1 for greater than.
            Returns NotImplemented for unimplemented cases
        """
        return self._binary_op(rhs, self._cmp_impl, full=True)

    def __lt__(self, rhs):
        """ Less Than."""
        return self.cmp(rhs) < 0

    def __le__(self, rhs):
        """ Less Than or Equal."""
        return self.cmp(rhs) <= 0

    def __eq__(self, rhs):
        """ Equal."""
        return self.cmp(rhs) == 0

    def __ne__(self, rhs):
        """ Not Equal."""
        return self.cmp(rhs) != 0

    def __gt__(self, rhs):
        """ Greater Than."""
        return self.cmp(rhs) > 0

    def __ge__(self, rhs):
        """ Greater Than or Equal."""
        return self.cmp(rhs) >= 0

    def __bool__(self):
        """ Convert to bool."""
        return bool(self.bits)

    def __str__(self):
        """ Get text representation."""
        # don't just use self.__float__() in order to work with numbers more
        # than 53 bits wide
        retval = "fixed:"
        bits = self.bits
        if bits < 0:
            retval += "-"
            bits = -bits
        int_part = bits >> self.fract_width
        fract_part = bits & ~(-1 << self.fract_width)
        # round up fract_width to nearest multiple of 4
        fract_width = (self.fract_width + 3) & ~3
        fract_part <<= (fract_width - self.fract_width)
        fract_width_in_hex_digits = fract_width // 4
        retval += f"0x{int_part:x}."
        if fract_width_in_hex_digits != 0:
            retval += f"{fract_part:x}".zfill(fract_width_in_hex_digits)
        return retval


class RootRemainder:
    """ A polynomial root and remainder.

    :attribute root: the polynomial root.
    :attribute remainder: the remainder.
    """

    def __init__(self, root, remainder):
        """ Create a new RootRemainder.

        :param root: the polynomial root.
        :param remainder: the remainder.
        """
        self.root = root
        self.remainder = remainder

    def __repr__(self):
        """ Get the representation as a string. """
        return f"RootRemainder({repr(self.root)}, {repr(self.remainder)})"

    def __str__(self):
        """ Convert to a string. """
        return f"RootRemainder({str(self.root)}, {str(self.remainder)})"


def fixed_sqrt(radicand):
    """ Compute the Square Root and Remainder.

    Solves the polynomial ``radicand - x * x == 0``

    :param radicand: the ``Fixed`` to take the square root of.
    :returns RootRemainder:
    """
    # Written for correctness, not speed
    if radicand < 0:
        return None
    is_int = isinstance(radicand, int)
    if is_int:
        radicand = Fixed(radicand, 0, radicand.bit_length() + 1, True)
    elif not isinstance(radicand, Fixed):
        raise TypeError()

    def is_remainder_non_negative(root):
        return radicand >= root * root

    root = radicand.with_bits(0)
    for i in reversed(range(root.bit_width)):
        new_root = root.with_bits(root.bits | (1 << i))
        if new_root < 0:  # skip sign bit
            continue
        if is_remainder_non_negative(new_root):
            root = new_root
    remainder = radicand - root * root
    if is_int:
        root = int(root)
        remainder = int(remainder)
    return RootRemainder(root, remainder)


class FixedSqrt:
    """ Fixed-point Square-Root/Remainder.

    :attribute radicand: the radicand
    :attribute root: the square root
    :attribute root_squared: the square of ``root``
    :attribute remainder: the remainder
    :attribute log2_radix: the base-2 log of the operation radix. The number of
        bits of root that are calculated per pipeline stage.
    :attribute current_shift: the current bit index
    """

    def __init__(self, radicand, log2_radix=3):
        """ Create an FixedSqrt.

        :param radicand: the radicand.
        :param log2_radix: the base-2 log of the operation radix. The number of
            bits of root that are calculated per pipeline stage.
        """
        assert isinstance(radicand, Fixed)
        assert radicand.signed is False
        self.radicand = radicand
        self.root = radicand.with_bits(0)
        self.root_squared = self.root * self.root
        self.remainder = radicand.with_bits(0) - self.root_squared
        self.log2_radix = log2_radix
        self.current_shift = self.root.bit_width

    def calculate_stage(self):
        """ Calculate the next pipeline stage of the operation.

        :returns bool: True if this is the last pipeline stage.
        """
        if self.current_shift == 0:
            return True
        log2_radix = min(self.log2_radix, self.current_shift)
        assert log2_radix > 0
        self.current_shift -= log2_radix
        radix = 1 << log2_radix
        trial_squares = []
        for i in range(radix):
            v = self.root_squared
            factor1 = Fixed.from_bits(i << (self.current_shift + 1),
                                      self.root.fract_width,
                                      self.root.bit_width + 1 + log2_radix,
                                      False)
            v += self.root * factor1
            factor2 = Fixed.from_bits(i << self.current_shift,
                                      self.root.fract_width,
                                      self.root.bit_width + log2_radix,
                                      False)
            v += factor2 * factor2
            trial_squares.append(self.root_squared.with_value(v))
        root_bits = 0
        new_root_squared = self.root_squared
        for i in range(radix):
            if self.radicand >= trial_squares[i]:
                root_bits = i
                new_root_squared = trial_squares[i]
        self.root |= Fixed.from_bits(root_bits << self.current_shift,
                                     self.root.fract_width,
                                     self.root.bit_width + log2_radix,
                                     False)
        self.root_squared = new_root_squared
        if self.current_shift == 0:
            self.remainder = self.radicand - self.root_squared
            return True
        return False

    def calculate(self):
        """ Calculate the results of the square root.

        :returns: self
        """
        while not self.calculate_stage():
            pass
        return self


def fixed_rsqrt(radicand):
    """ Compute the Reciprocal Square Root and Remainder.

    Solves the polynomial ``1 - x * x * radicand == 0``

    :param radicand: the ``Fixed`` to take the reciprocal square root of.
    :returns RootRemainder:
    """
    # Written for correctness, not speed
    if radicand <= 0:
        return None
    if not isinstance(radicand, Fixed):
        raise TypeError()

    def is_remainder_non_negative(root):
        return 1 >= root * root * radicand

    root = radicand.with_bits(0)
    for i in reversed(range(root.bit_width)):
        new_root = root.with_bits(root.bits | (1 << i))
        if new_root < 0:  # skip sign bit
            continue
        if is_remainder_non_negative(new_root):
            root = new_root
    remainder = 1 - root * root * radicand
    return RootRemainder(root, remainder)


class FixedRSqrt:
    """ Fixed-point Reciprocal-Square-Root/Remainder.

    :attribute radicand: the radicand
    :attribute root: the reciprocal square root
    :attribute radicand_root: ``radicand * root``
    :attribute radicand_root_squared: ``radicand * root * root``
    :attribute remainder: the remainder
    :attribute log2_radix: the base-2 log of the operation radix. The number of
        bits of root that are calculated per pipeline stage.
    :attribute current_shift: the current bit index
    """

    def __init__(self, radicand, log2_radix=3):
        """ Create an FixedRSqrt.

        :param radicand: the radicand.
        :param log2_radix: the base-2 log of the operation radix. The number of
            bits of root that are calculated per pipeline stage.
        """
        assert isinstance(radicand, Fixed)
        assert radicand.signed is False
        self.radicand = radicand
        self.root = radicand.with_bits(0)
        self.radicand_root = radicand.with_bits(0) * self.root
        self.radicand_root_squared = self.radicand_root * self.root
        self.remainder = radicand.with_bits(0) - self.radicand_root_squared
        self.log2_radix = log2_radix
        self.current_shift = self.root.bit_width

    def calculate_stage(self):
        """ Calculate the next pipeline stage of the operation.

        :returns bool: True if this is the last pipeline stage.
        """
        if self.current_shift == 0:
            return True
        log2_radix = min(self.log2_radix, self.current_shift)
        assert log2_radix > 0
        self.current_shift -= log2_radix
        radix = 1 << log2_radix
        trial_values = []
        for i in range(radix):
            v = self.radicand_root_squared
            factor1 = Fixed.from_bits(i << (self.current_shift + 1),
                                      self.root.fract_width,
                                      self.root.bit_width + 1 + log2_radix,
                                      False)
            v += self.radicand_root * factor1
            factor2 = Fixed.from_bits(i << self.current_shift,
                                      self.root.fract_width,
                                      self.root.bit_width + log2_radix,
                                      False)
            v += self.radicand * factor2 * factor2
            trial_values.append(self.radicand_root_squared.with_value(v))
        root_bits = 0
        new_radicand_root_squared = self.radicand_root_squared
        for i in range(radix):
            if 1 >= trial_values[i]:
                root_bits = i
                new_radicand_root_squared = trial_values[i]
        v = self.radicand_root
        v += self.radicand * Fixed.from_bits(root_bits << self.current_shift,
                                             self.root.fract_width,
                                             self.root.bit_width + log2_radix,
                                             False)
        self.radicand_root = self.radicand_root.with_value(v)
        self.root |= Fixed.from_bits(root_bits << self.current_shift,
                                     self.root.fract_width,
                                     self.root.bit_width + log2_radix,
                                     False)
        self.radicand_root_squared = new_radicand_root_squared
        if self.current_shift == 0:
            self.remainder = 1 - self.radicand_root_squared
            return True
        return False

    def calculate(self):
        """ Calculate the results of the reciprocal square root.

        :returns: self
        """
        while not self.calculate_stage():
            pass
        return self


class Operation(enum.Enum):
    """ Operation for ``FixedUDivRemSqrtRSqrt``. """

    UDivRem = "unsigned-divide/remainder"
    SqrtRem = "square-root/remainder"
    RSqrtRem = "reciprocal-square-root/remainder"


class FixedUDivRemSqrtRSqrt:
    """ Combined class for computing fixed-point unsigned div/rem/sqrt/rsqrt.

    Algorithm based on ``UnsignedDivRem``, ``FixedSqrt``, and ``FixedRSqrt``.

    Formulas solved are:
    * div/rem:
        ``dividend == quotient_root * divisor_radicand``
    * sqrt/rem:
        ``divisor_radicand == quotient_root * quotient_root``
    * rsqrt/rem:
        ``1 == quotient_root * quotient_root * divisor_radicand``

    The remainder is the left-hand-side of the comparison minus the
    right-hand-side of the comparison in the above formulas.

    Important: not all variables have the same bit-width or fract-width. For
        instance, ``dividend`` has a bit-width of ``bit_width + fract_width``
        and a fract-width of ``2 * fract_width`` bits.

    :attribute dividend: dividend for div/rem. Variable with a bit-width of
        ``bit_width + fract_width`` and a fract-width of ``fract_width * 2``
        bits.
    :attribute divisor_radicand: divisor for div/rem and radicand for
        sqrt/rsqrt. Variable with a bit-width of ``bit_width`` and a
        fract-width of ``fract_width`` bits.
    :attribute operation: the ``Operation`` to be computed.
    :attribute quotient_root: the quotient or root part of the result of the
        operation. Variable with a bit-width of ``bit_width`` and a fract-width
        of ``fract_width`` bits.
    :attribute remainder: the remainder part of the result of the operation.
        Variable with a bit-width of ``bit_width * 3`` and a fract-width
        of ``fract_width * 3`` bits.
    :attribute root_times_radicand: ``quotient_root * divisor_radicand``.
        Variable with a bit-width of ``bit_width * 2`` and a fract-width of
        ``fract_width * 2`` bits.
    :attribute compare_lhs: The left-hand-side of the comparison in the
        equation to be solved. Variable with a bit-width of ``bit_width * 3``
        and a fract-width of ``fract_width * 3`` bits.
    :attribute compare_rhs: The right-hand-side of the comparison in the
        equation to be solved. Variable with a bit-width of ``bit_width * 3``
        and a fract-width of ``fract_width * 3`` bits.
    :attribute bit_width: base bit-width. Constant int.
    :attribute fract_width: base fract-width. Specifies location of base-2
        radix point. Constant int.
    :attribute log2_radix: number of bits of ``quotient_root`` that should be
        computed per pipeline stage (invocation of ``calculate_stage``).
        Constant int.
    :attribute current_shift: the current bit index. Variable int.
    """

    def __init__(self,
                 dividend,
                 divisor_radicand,
                 operation,
                 bit_width,
                 fract_width,
                 log2_radix):
        """ Create a new ``FixedUDivRemSqrtRSqrt``.

        :param dividend: ``dividend`` attribute's initializer.
        :param divisor_radicand: ``divisor_radicand`` attribute's initializer.
        :param operation: ``operation`` attribute's initializer.
        :param bit_width: ``bit_width`` attribute's initializer.
        :param fract_width: ``fract_width`` attribute's initializer.
        :param log2_radix: ``log2_radix`` attribute's initializer.
        """
        assert bit_width > 0
        assert fract_width >= 0
        assert fract_width <= bit_width
        assert log2_radix > 0
        self.dividend = Const.normalize(dividend,
                                        (bit_width + fract_width, False))
        self.divisor_radicand = Const.normalize(divisor_radicand,
                                                (bit_width, False))
        self.quotient_root = 0
        self.root_times_radicand = 0
        if operation is Operation.UDivRem:
            self.compare_lhs = self.dividend << fract_width
        elif operation is Operation.SqrtRem:
            self.compare_lhs = self.divisor_radicand << (fract_width * 2)
        else:
            assert operation is Operation.RSqrtRem
            self.compare_lhs = 1 << (fract_width * 3)
        self.compare_rhs = 0
        self.remainder = self.compare_lhs
        self.operation = operation
        self.bit_width = bit_width
        self.fract_width = fract_width
        self.log2_radix = log2_radix
        self.current_shift = bit_width

    def calculate_stage(self):
        """ Calculate the next pipeline stage of the operation.

        :returns bool: True if this is the last pipeline stage.
        """
        if self.current_shift == 0:
            return True
        log2_radix = min(self.log2_radix, self.current_shift)
        assert log2_radix > 0
        self.current_shift -= log2_radix
        radix = 1 << log2_radix
        trial_compare_rhs_values = []
        for trial_bits in range(radix):
            shifted_trial_bits = trial_bits << self.current_shift
            shifted_trial_bits_sqrd = shifted_trial_bits * shifted_trial_bits
            v = self.compare_rhs
            if self.operation is Operation.UDivRem:
                factor1 = self.divisor_radicand * shifted_trial_bits
                v += factor1 << self.fract_width
            elif self.operation is Operation.SqrtRem:
                factor1 = self.quotient_root * (shifted_trial_bits << 1)
                v += factor1 << self.fract_width
                factor2 = shifted_trial_bits_sqrd
                v += factor2 << self.fract_width
            else:
                assert self.operation is Operation.RSqrtRem
                factor1 = self.root_times_radicand * (shifted_trial_bits << 1)
                v += factor1
                factor2 = self.divisor_radicand * shifted_trial_bits_sqrd
                v += factor2
            trial_compare_rhs_values.append(v)
        shifted_next_bits = 0
        next_compare_rhs = trial_compare_rhs_values[0]
        for trial_bits in range(radix):
            if self.compare_lhs >= trial_compare_rhs_values[trial_bits]:
                shifted_next_bits = trial_bits << self.current_shift
                next_compare_rhs = trial_compare_rhs_values[trial_bits]
        self.root_times_radicand += self.divisor_radicand * shifted_next_bits
        self.compare_rhs = next_compare_rhs
        self.quotient_root |= shifted_next_bits
        self.remainder = self.compare_lhs - self.compare_rhs
        return self.current_shift == 0

    def calculate(self):
        """ Calculate the results of the operation.

        :returns: self
        """
        while not self.calculate_stage():
            pass
        return self

""" DivPipeOp enum for all operations the division pipeline can execute
"""
import enum


class DivPipeOp(enum.IntEnum):
    """ The enumeration of operations that the division pipeline can execute

    Integer division and remainder use truncating division (quotient
    rounded towards zero -- the standard for Rust and C/C++) rather than
    Python's standard flooring division (quotient rounded towards negative
    infinity). This means that signed integer remainder takes its sign from the
    dividend instead of the divisor.
    """

    DivS64High = 0
    """ Signed 64-bit integer shifted left by 64-bits divided by 64-bit integer
        producing 64-bit integer quotient.

        quotient = i64((i64(dividend) << 64) / i64(divisor))

        Power instruction: divde
    """

    DivU64High = enum.auto()
    """ Unsigned 64-bit Integer shifted left by 64-bits by 64-bit producing
        64-bit quotient.

        quotient = u64((u64(dividend) << 64) / u64(divisor))

        Power instruction: divdeu
    """

    DivS64 = enum.auto()
    """ Signed 64-bit Integer by 64-bit producing 64-bit quotient.

        quotient = i64(i64(dividend) / i64(divisor))

        Power instruction: divd
        RV64 instruction: div
    """

    DivU64 = enum.auto()
    """ Signed 64-bit Integer by 64-bit producing 64-bit quotient.

        quotient = i64(i64(dividend) / i64(divisor))

        Power instruction: divdu
        RV64 instruction: divu
    """

    RemS64 = enum.auto()
    """ Signed 64-bit Integer by 64-bit producing 64-bit remainder.

        remainder = i64(i64(dividend) % i64(divisor))

        Power instruction: modsd
        RV64 instruction: rem
    """

    RemU64 = enum.auto()
    """ Unsigned 64-bit Integer by 64-bit producing 64-bit remainder.

        remainder = u64(u64(dividend) % u64(divisor))

        Power instruction: modud
        RV64 instruction: remu
    """

    DivS32High = enum.auto()
    """ Signed 32-bit integer shifted left by 32-bits divided by 32-bit integer
        producing 32-bit integer quotient.

        quotient = i32((i32(dividend) << 32) / i32(divisor))

        Power instruction: divwe
    """

    DivU32High = enum.auto()
    """ Unsigned 32-bit Integer shifted left by 32-bits by 32-bit producing
        32-bit quotient.

        quotient = u32((u32(dividend) << 32) / u32(divisor))

        Power instruction: divweu
    """

    DivS32 = enum.auto()
    """ Signed 32-bit Integer by 32-bit producing 32-bit quotient.

        quotient = i32(i32(dividend) / i32(divisor))

        Power instruction: divw
        RV64 instruction: divw
    """

    DivU32 = enum.auto()
    """ Signed 32-bit Integer by 32-bit producing 32-bit quotient.

        quotient = i32(i32(dividend) / i32(divisor))

        Power instruction: divwu
        RV64 instruction: divuw
    """

    RemS32 = enum.auto()
    """ Signed 32-bit Integer by 32-bit producing 32-bit remainder.

        remainder = i32(i32(dividend) % i32(divisor))

        Power instruction: modsw
        RV64 instruction: remw
    """

    RemU32 = enum.auto()
    """ Unsigned 32-bit Integer by 32-bit producing 32-bit remainder.

        remainder = u32(u32(dividend) % u32(divisor))

        Power instruction: moduw
        RV64 instruction: remuw
    """

    # FIXME(programmerjake): add FP operations

    # DivF16 = enum.auto()
    # """ 16-bit IEEE 754 Floating-point division.
    #
    #     quotient = f16(f16(dividend) / f16(divisor))
    # """
    #
    # DivF32 = enum.auto()
    # """ 32-bit IEEE 754 Floating-point division.
    #
    #     quotient = f32(f32(dividend) / f32(divisor))
    # """
    #
    # DivF64 = enum.auto()
    # """ 64-bit IEEE 754 Floating-point division.
    #
    #     quotient = f64(f64(dividend) / f64(divisor))
    # """
    #
    # SqrtF16 = enum.auto()
    # """ 16-bit IEEE 754 Floating-point square root.
    #
    #     quotient = f16(sqrt(f16(dividend)))
    # """
    #
    # SqrtF32 = enum.auto()
    # """ 32-bit IEEE 754 Floating-point square root.
    #
    #     quotient = f32(sqrt(f32(dividend)))
    # """
    #
    # SqrtF64 = enum.auto()
    # """ 64-bit IEEE 754 Floating-point square root.
    #
    #     quotient = f64(sqrt(f64(dividend)))
    # """
    #
    # RSqrtF16 = enum.auto()
    # """ 16-bit IEEE 754 Floating-point reciprocal square root.
    #
    #     quotient = f16(1 / sqrt(f16(dividend)))
    # """
    #
    # RSqrtF32 = enum.auto()
    # """ 32-bit IEEE 754 Floating-point reciprocal square root.
    #
    #     quotient = f32(1 / sqrt(f32(dividend)))
    # """
    #
    # RSqrtF64 = enum.auto()
    # """ 64-bit IEEE 754 Floating-point reciprocal square root.
    #
    #     quotient = f64(1 / sqrt(f64(dividend)))
    # """

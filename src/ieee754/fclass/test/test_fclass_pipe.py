""" test of FPClassMuxInOut
"""

from ieee754.fclass.pipeline import (FPClassMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp
from ieee754.fpcommon.fpbase import FPFormat

import sfpy
from sfpy import Float64, Float32, Float16

def fclass(wid, x):
    x = x.bits
    fmt = FPFormat.standard(wid)
    print (hex(x), "exp", fmt.get_exponent(x), fmt.emax,
                    "m", hex(fmt.get_mantissa(x)),
                    fmt.get_mantissa(x) & (1<<fmt.m_width-1))
    if fmt.is_inf(x):
        if fmt.get_sign(x):
            return 1<<0
        else:
            return 1<<7
    if fmt.is_zero(x):
        if fmt.get_sign(x):
            return 1<<3
        else:
            return 1<<4
    if fmt.get_exponent(x) == fmt.emax and fmt.get_mantissa(x) != 0:
        if fmt.is_nan_signalling(x):
            return 1<<8
        else:
            return 1<<9
    if fmt.is_subnormal(x) and fmt.get_mantissa(x) != 0:
        if fmt.get_sign(x):
            return 1<<2
        else:
            return 1<<5
    if fmt.get_sign(x):
        return 1<<1
    else:
        return 1<<6


def fclass_16(x):
    return fclass(16, x)


def fclass_32(x):
    return fclass(32, x)


def fclass_64(x):
    return fclass(64, x)


def test_class_pipe_f16():
    dut = FPClassMuxInOut(16, 16, 4, op_wid=1)
    runfp(dut, 16, "test_fclass_pipe_f16", Float16, fclass_16,
                True, n_vals=100)


def test_class_pipe_f32():
    dut = FPClassMuxInOut(32, 32, 4, op_wid=1)
    runfp(dut, 32, "test_fclass_pipe_f32", Float32, fclass_32,
                True, n_vals=100)


def test_class_pipe_f64():
    dut = FPClassMuxInOut(64, 64, 4, op_wid=1)
    runfp(dut, 64, "test_fclass_pipe_f64", Float64, fclass_64,
                True, n_vals=100)


if __name__ == '__main__':
    for i in range(200):
        test_class_pipe_f16()
        test_class_pipe_f32()
        test_class_pipe_f64()

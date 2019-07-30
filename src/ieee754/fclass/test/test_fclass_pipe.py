""" test of FPClassMuxInOut
"""

from ieee754.fclass.pipeline import (FPClassMuxInOut,)
from ieee754.fpcommon.test.fpmux import runfp
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_half
from ieee754.fpcommon.fpbase import FPFormat

import unittest

import sfpy
from sfpy import Float64, Float32, Float16


def fclass(wid, x):
    """ analyses the FP number and returns a RISC-V "FCLASS" unary bitfield

        this is easy to understand however it has redundant checks (which
        don't matter because performance of *testing* is not hardware-critical)
        see FPClassMod for a hardware-optimal (hard-to-read) version
    """
    x = x.bits
    fmt = FPFormat.standard(wid)
    print (hex(x), "exp", fmt.get_exponent(x), fmt.e_max,
                    "m", hex(fmt.get_mantissa_field(x)),
                    fmt.get_mantissa_field(x) & (1<<fmt.m_width-1))
    if fmt.is_inf(x):
        if fmt.get_sign_field(x):
            return 1<<0
        else:
            return 1<<7
    if fmt.is_zero(x):
        if fmt.get_sign_field(x):
            return 1<<3
        else:
            return 1<<4
    if fmt.get_exponent(x) == fmt.e_max and fmt.get_mantissa_field(x) != 0:
        if fmt.is_nan_signaling(x):
            return 1<<8
        else:
            return 1<<9
    if fmt.is_subnormal(x) and fmt.get_mantissa_field(x) != 0:
        if fmt.get_sign_field(x):
            return 1<<2
        else:
            return 1<<5
    if fmt.get_sign_field(x):
        return 1<<1
    else:
        return 1<<6


def fclass_16(x):
    return fclass(16, x)


def fclass_32(x):
    return fclass(32, x)


def fclass_64(x):
    return fclass(64, x)


class TestFClassPipe(unittest.TestCase):
    def test_class_pipe_f16(self):
        dut = FPClassMuxInOut(16, 16, 4, op_wid=1)
        runfp(dut, 16, "test_fclass_pipe_f16", Float16, fclass_16,
                    True, n_vals=100)

    def test_class_pipe_f32(self):
        dut = FPClassMuxInOut(32, 32, 4, op_wid=1)
        runfp(dut, 32, "test_fclass_pipe_f32", Float32, fclass_32,
                    True, n_vals=100)

    def test_class_pipe_f64(self):
        dut = FPClassMuxInOut(64, 64, 4, op_wid=1)
        runfp(dut, 64, "test_fclass_pipe_f64", Float64, fclass_64,
                    True, n_vals=100)


class TestFClassPipeCoverage(unittest.TestCase):
    def test_pipe_class_f16(self):
        dut = FPClassMuxInOut(16, 16, 4, op_wid=1)
        run_pipe_fp(dut, 16, "fclass16", unit_test_half, Float16, None,
                    fclass_16, 100, single_op=True)

    def test_pipe_class_f32(self):
        dut = FPClassMuxInOut(32, 32, 4, op_wid=1)
        run_pipe_fp(dut, 32, "fclass32", unit_test_half, Float32, None,
                    fclass_32, 100, single_op=True)

    def test_pipe_class_f64(self):
        dut = FPClassMuxInOut(64, 64, 4, op_wid=1)
        run_pipe_fp(dut, 64, "fclass64", unit_test_half, Float64, None,
                    fclass_64, 100, single_op=True)


if __name__ == '__main__':
    unittest.main()

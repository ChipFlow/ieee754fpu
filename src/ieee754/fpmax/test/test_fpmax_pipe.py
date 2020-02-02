""" test of FPCVTMuxInOut
"""

from ieee754.fpmax.pipeline import (FPMAXMuxInOut)
from ieee754.fpcommon.test.fpmux import runfp
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_single

from sfpy import Float16, Float32, Float64
import math


def fpmax_f32_max(a, b):
    # Apparently, sfpy doesn't include a min or max function. Python's
    # min/max work, however python min/max are not IEEE754 Compliant
    # (namely, they don't behave correctly with NaNs
    # IEEE754 defines max(num, NaN) and max(NaN, num) as both
    # returning num (and the same for min)
    if math.isnan(a) or math.isnan(b):
        if math.isnan(a) and math.isnan(b):
            return Float32(float('nan'))
        else:
            return b if math.isnan(a) else a
    if a.bits & (1<<31) != b.bits & (1<<31):
        return b if a.bits & (1<<31) else a
    elif a > b:
        return a
    else:
        return b


def fpmax_f32_min(a, b):
    if math.isnan(a) or math.isnan(b):
        if math.isnan(a) and math.isnan(b):
            return Float32(float('nan'))
        else:
            return b if math.isnan(a) else a
    if a.bits & (1<<31) != b.bits & (1<<31):
        return a if a.bits & (1<<31) else b
    elif a < b:
        return a
    else:
        return b


def test_fpmax_f32_max():
    dut = FPMAXMuxInOut(32, 4)
    runfp(dut, 32, "test_fpmax_f32_max", Float32, fpmax_f32_max,
          n_vals=100, opcode=0x0)


def test_fpmax_f32_min():
    dut = FPMAXMuxInOut(32, 4)
    runfp(dut, 32, "test_fpmax_f32_min", Float32, fpmax_f32_min,
          n_vals=100, opcode=0x1)

def nan_testcases():
    nan = Float32(float('nan')).bits
    yield nan, Float32(1.0).bits
    yield Float32(1.0).bits, nan
    yield nan, nan
    yield Float32(0.0).bits, Float32(-0.0).bits
    yield Float32(-0.0).bits, Float32(0.0).bits

def test_fpmax_f32_nans():
    dut = FPMAXMuxInOut(32, 4)
    run_pipe_fp(dut, 32, "test_fpmax_f32_max_nans", unit_test_single,
                Float32, nan_testcases, fpmax_f32_max, 5,
                opcode=0b0)
    run_pipe_fp(dut, 32, "test_fpmax_f32_min_nans", unit_test_single,
                Float32, nan_testcases, fpmax_f32_min, 5,
                opcode=0b1)


if __name__ == '__main__':
    test_fpmax_f32_nans()
    for i in range(50):
        test_fpmax_f32_max()
        test_fpmax_f32_min()

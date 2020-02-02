""" test of FPCVTMuxInOut
"""

from ieee754.fpmax.pipeline import (FPMAXMuxInOut)
from ieee754.fpcommon.test.fpmux import runfp

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
    if a > b:
        return a
    else:
        return b


def fpmax_f32_min(a, b):
    if math.isnan(a) or math.isnan(b):
        if math.isnan(a) and math.isnan(b):
            return Float32(float('nan'))
        else:
            return b if math.isnan(a) else a
    if a < b:
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


if __name__ == '__main__':
    for i in range(50):
        test_fpmax_f32_max()
        test_fpmax_f32_min()

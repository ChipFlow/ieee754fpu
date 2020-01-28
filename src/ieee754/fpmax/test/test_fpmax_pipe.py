""" test of FPCVTMuxInOut
"""

from ieee754.fpmax.pipeline import (FPMAXMuxInOut)
from ieee754.fpcommon.test.fpmux import runfp

from sfpy import Float16, Float32, Float64
import math


def fpmax_f32_max(a, b):
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
        test_fpmax_f32_min()
        test_fpmax_f32_max()

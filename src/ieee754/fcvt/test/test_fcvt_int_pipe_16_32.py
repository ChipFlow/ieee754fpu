""" test of FPCVTIntMuxInOut.

    this one still uses the run_pipe_fp infrastructure which assumes
    that it's being passed FP input.  it doesn't make a heck of a lot
    of sense, but hey.
"""

from ieee754.fcvt.pipeline import (FPCVTIntMuxInOut,)
from ieee754.fpcommon.test.case_gen import run_pipe_fp
from ieee754.fpcommon.test import unit_test_half
from ieee754.fcvt.test.up_fcvt_data_16_32 import regressions

import sfpy
from sfpy import Float64, Float32, Float16

def to_uint16(x):
    return x

def to_uint32(x):
    return x

def fcvt_64(x):
    return sfpy.float.ui32_to_f64(x)

def fcvt_32(x):
    return sfpy.float.ui32_to_f32(x)

def test_int_pipe_fp16_32():
    dut = FPCVTIntMuxInOut(16, 32, 4)
    run_pipe_fp(dut, 16, "int_16_32", unit_test_half, to_uint16,
                regressions, fcvt_32, 100, True)

if __name__ == '__main__':
    for i in range(200):
        test_int_pipe_fp16_32()

